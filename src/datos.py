"""
Capas de datos para el monitor de incendios. Todas públicas, ninguna pide clave.

Cada función cachea en ./data, así que la segunda corrida es instantánea.
"""

from __future__ import annotations

import gzip
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parents[1]
CACHE = RAIZ / "data"
CACHE.mkdir(exist_ok=True)

# Perú continental: UTM 18S. Áreas y distancias NUNCA en EPSG:4326.
CRS_METRICO = "EPSG:32718"


def _bajar(url: str, destino: Path, timeout: int = 900) -> Path:
    if destino.exists() and destino.stat().st_size > 0:
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        tmp = destino.with_suffix(destino.suffix + ".parcial")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
        tmp.replace(destino)
    return destino


def a_metros(gdf):
    return gdf.to_crs(CRS_METRICO)


# --------------------------------------------------------------------------
# 1 · Límites distritales (INEI con UBIGEO, vía peru-geojson)
# --------------------------------------------------------------------------
URL_DISTRITOS = ("https://raw.githubusercontent.com/juaneladio/peru-geojson"
                 "/master/peru_distrital_simple.geojson")


def distritos() -> gpd.GeoDataFrame:
    """1 874 distritos con UBIGEO, EPSG:4326."""
    ruta = _bajar(URL_DISTRITOS, CACHE / "peru_distrital.geojson")
    gdf = gpd.read_file(ruta)
    ren = {"NOMBDEP": "departamento", "NOMBPROV": "provincia",
           "NOMBDIST": "distrito", "IDDPTO": "iddpto", "IDDIST": "ubigeo"}
    gdf = gdf.rename(columns={k: v for k, v in ren.items() if k in gdf.columns})
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    return gdf.to_crs("EPSG:4326")


def distrito(nombre: str, departamento: str | None = None) -> gpd.GeoDataFrame:
    """Un distrito por nombre (y departamento si el nombre se repite)."""
    d = distritos()
    sel = d[d["distrito"].str.upper() == nombre.upper()]
    if departamento:
        sel = sel[sel["departamento"].str.upper() == departamento.upper()]
    if sel.empty:
        raise ValueError(f"No encontré el distrito {nombre!r}")
    return sel


# --------------------------------------------------------------------------
# 2 · Focos de calor — NASA FIRMS, descarga pública de 7 días (sin MAP_KEY)
# --------------------------------------------------------------------------
FIRMS_7D = {
    "viirs-snpp": ("https://firms.modaps.eosdis.nasa.gov/data/active_fire/"
                   "suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_South_America_7d.csv"),
    "viirs-noaa20": ("https://firms.modaps.eosdis.nasa.gov/data/active_fire/"
                     "noaa-20-viirs-c2/csv/J1_VIIRS_C2_South_America_7d.csv"),
    "viirs-noaa21": ("https://firms.modaps.eosdis.nasa.gov/data/active_fire/"
                     "noaa-21-viirs-c2/csv/J2_VIIRS_C2_South_America_7d.csv"),
    "modis": ("https://firms.modaps.eosdis.nasa.gov/data/active_fire/"
              "modis-c6.1/csv/MODIS_C6_1_South_America_7d.csv"),
}

# caja del Perú continental
PERU_BBOX = (-81.5, -18.5, -68.5, -0.0)


def focos_7d(sensor: str = "viirs-snpp",
             solo_peru: bool = True,
             confianza_minima: str = "n") -> gpd.GeoDataFrame:
    """
    Focos de calor de los últimos 7 días. Descarga pública, sin credenciales.

    `confianza_minima`: 'l' deja todo, 'n' descarta los de confianza baja
    (recomendado: los 'l' incluyen reflejos, antorchas de gas y falsos positivos).
    """
    url = FIRMS_7D[sensor]
    ruta = _bajar(url, CACHE / f"firms_{sensor}_7d.csv")
    df = pd.read_csv(ruta)
    df.columns = [c.lower() for c in df.columns]

    if solo_peru:
        x0, y0, x1, y1 = PERU_BBOX
        df = df[df.longitude.between(x0, x1) & df.latitude.between(y0, y1)]

    # FIRMS escribe la confianza de dos formas segun el producto: letras
    # (l/n/h) en la API por pais, palabras (low/nominal/high) en el CSV de
    # 7 dias. Normalizamos a letra antes de filtrar.
    if "confidence" in df:
        conf = df["confidence"].astype(str).str.strip().str.lower()
        df = df.assign(conf=conf.str[0])        # low->l, nominal->n, high->h
        if confianza_minima == "n":
            df = df[df["conf"].isin(["n", "h"])]

    df["momento"] = pd.to_datetime(
        df["acq_date"].astype(str) + " " +
        df["acq_time"].astype(str).str.zfill(4),
        format="%Y-%m-%d %H%M", utc=True)

    return gpd.GeoDataFrame(
        df.reset_index(drop=True),
        geometry=gpd.points_from_xy(df.longitude, df.latitude),
        crs="EPSG:4326")


def agrupar_incendios(focos: gpd.GeoDataFrame,
                      radio_km: float = 1.0,
                      horas: float = 48.0) -> gpd.GeoDataFrame:
    """
    Agrupa focos en incendios: dos focos son el mismo evento si están a menos
    de `radio_km` y a menos de `horas` de distancia. Es la regla del profesor,
    implementada como DBSCAN en un espacio donde el tiempo se convierte a metros.
    """
    from sklearn.cluster import DBSCAN

    g = a_metros(focos)
    t0 = focos["momento"].min()
    # 1 hora ≡ radio_km*1000/horas metros → un solo eps para espacio y tiempo
    escala = radio_km * 1000 / horas
    horas_desde = (focos["momento"] - t0).dt.total_seconds().values / 3600

    X = np.column_stack([g.geometry.x, g.geometry.y, horas_desde * escala])
    etiquetas = DBSCAN(eps=radio_km * 1000, min_samples=1).fit_predict(X)

    out = focos.copy()
    out["incendio_id"] = etiquetas
    return out


def resumen_incendios(focos_agrupados: gpd.GeoDataFrame,
                      buffer_m: float = 375.0) -> gpd.GeoDataFrame:
    """Una fila por incendio: focos, FRP, duración y huella aproximada."""
    g = a_metros(focos_agrupados)
    filas = []
    for iid, grupo in g.groupby("incendio_id"):
        huella = grupo.buffer(buffer_m).union_all()
        centro = huella.centroid
        filas.append({
            "incendio_id": iid,
            "n_focos": len(grupo),
            "frp_total": grupo["frp"].sum(),
            "frp_max": grupo["frp"].max(),
            "inicio": grupo["momento"].min(),
            "fin": grupo["momento"].max(),
            "horas": (grupo["momento"].max() - grupo["momento"].min())
                      .total_seconds() / 3600,
            "huella_ha": huella.area / 1e4,
            "lon": centro.x, "lat": centro.y,
            "geometry": huella,
        })
    res = gpd.GeoDataFrame(filas, geometry="geometry", crs=CRS_METRICO)
    # el centroide se calcula en metros y SOLO despues se pasa a grados
    centros = res.geometry.centroid.to_crs(4326)
    res["lon"], res["lat"] = centros.x.values, centros.y.values
    return res.sort_values("frp_total", ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------
# 3 · Microsoft Planetary Computer — Sentinel-2 y WorldCover
# --------------------------------------------------------------------------
PC_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"


def catalogo():
    import planetary_computer
    import pystac_client
    return pystac_client.Client.open(PC_STAC, modifier=planetary_computer.sign_inplace)


def buscar_sentinel2(bbox, inicio: str, fin: str, nubes_max: int = 60):
    """Escenas Sentinel-2 L2A que tocan `bbox` entre dos fechas (YYYY-MM-DD)."""
    items = list(catalogo().search(
        collections=["sentinel-2-l2a"],
        bbox=bbox,
        datetime=f"{inicio}/{fin}",
        query={"eo:cloud_cover": {"lt": nubes_max}},
    ).items())
    items.sort(key=lambda i: i.datetime)
    return items


def tabla_escenas(items) -> pd.DataFrame:
    """Fecha y nubosidad de cada escena: lo que hay que reportar siempre."""
    return pd.DataFrame([{
        "id": i.id,
        "fecha": i.datetime.date(),
        "nubes_escena_pct": i.properties.get("eo:cloud_cover"),
        "mgrs": i.properties.get("s2:mgrs_tile"),
    } for i in items])


BANDAS_NBR = ["B08", "B12", "SCL"]
# SCL: clases que NO sirven (nube, sombra de nube, cirro, nieve, saturado, sin dato)
SCL_MALAS = {0, 1, 3, 8, 9, 10, 11}


def leer_bandas(item, bbox, resolucion: int = 20):
    """Lee B08, B12 y SCL de una escena, recortadas a bbox, en EPSG:32718."""
    import odc.stac

    ds = odc.stac.load(
        [item], bands=BANDAS_NBR, bbox=bbox,
        crs=CRS_METRICO, resolution=resolucion, chunks={},
    ).isel(time=0)
    return ds.compute()


def nbr(ds):
    """NBR = (NIR - SWIR2) / (NIR + SWIR2), enmascarado por nubes con SCL."""
    nir = ds["B08"].astype("float32")
    swir = ds["B12"].astype("float32")
    val = (nir - swir) / (nir + swir)
    mascara = ~ds["SCL"].isin(list(SCL_MALAS))
    return val.where(mascara)


def pct_nubes(ds) -> float:
    """% de píxeles inutilizables dentro del recorte (no de la escena entera)."""
    malas = ds["SCL"].isin(list(SCL_MALAS))
    return float(malas.mean()) * 100


# Severidad dNBR, umbrales de Key & Benson (USGS)
SEVERIDAD = [
    ("Rebrote",            -np.inf, -0.10),
    ("Sin cambio",          -0.10,   0.10),
    ("Severidad baja",       0.10,   0.27),
    ("Severidad moderada-baja", 0.27, 0.44),
    ("Severidad moderada-alta", 0.44, 0.66),
    ("Severidad alta",       0.66,   np.inf),
]
UMBRAL_QUEMADO = 0.27  # desde "moderada-baja" se considera quemado


def hectareas_por_severidad(dnbr, resolucion: int = 20) -> pd.DataFrame:
    """Hectáreas en cada clase de severidad. Reporta siempre el umbral usado."""
    ha_px = (resolucion ** 2) / 10_000
    v = dnbr.values
    v = v[np.isfinite(v)]
    filas = [{"clase": n, "dnbr_min": a, "dnbr_max": b,
              "hectareas": float(((v >= a) & (v < b)).sum() * ha_px)}
             for n, a, b in SEVERIDAD]
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------
# 4 · ESA WorldCover 10 m (qué se quemó)
# --------------------------------------------------------------------------
WORLDCOVER_CLASES = {
    10: "Bosque", 20: "Matorral", 30: "Pastizal", 40: "Agricultura",
    50: "Área construida", 60: "Suelo desnudo", 70: "Nieve/hielo",
    80: "Agua", 90: "Humedal herbáceo", 95: "Manglar", 100: "Musgo y liquen",
}


def worldcover(bbox=None, resolucion: int = 20, like=None):
    """
    Mosaico de WorldCover 2021 desde Planetary Computer.

    Con `like=<dataset de Sentinel-2>` se carga sobre EXACTAMENTE la misma
    grilla: mismo CRS, mismo transform, mismo ancho y alto. Es la unica forma
    de cruzar dos raster sin reproyectar despues, y evita el error clasico de
    operar arrays que vienen de grillas distintas.

    WorldCover es categorico, asi que el remuestreo es nearest-neighbor
    (el de odc.stac por defecto): promediar codigos de clase no significa nada.
    """
    import odc.stac

    if like is None and bbox is None:
        raise ValueError("pasa bbox o like")

    caja = bbox if bbox is not None else tuple(
        gpd.GeoSeries([_caja_de(like)], crs=like.odc.crs.to_epsg()
                      if hasattr(like, "odc") else CRS_METRICO)
        .to_crs(4326).total_bounds)

    items = list(catalogo().search(
        collections=["esa-worldcover"], bbox=caja).items())
    items = [i for i in items if i.datetime.year == 2021] or items

    if like is not None:
        ds = odc.stac.load(items, bands=["map"], like=like,
                           resampling="nearest", chunks={})
    else:
        ds = odc.stac.load(items, bands=["map"], bbox=caja, crs=CRS_METRICO,
                           resolution=resolucion, resampling="nearest",
                           chunks={})
    if "time" in ds.dims:
        ds = ds.isel(time=0)
    return ds["map"].compute()


def _caja_de(ds):
    """Bounding box (shapely) de un dataset cargado con odc.stac."""
    from shapely.geometry import box as _box
    x, y = ds["x"].values, ds["y"].values
    return _box(float(x.min()), float(y.min()), float(x.max()), float(y.max()))


def misma_grilla(a, b) -> bool:
    """
    Comprueba que dos raster comparten grilla antes de operarlos juntos:
    mismo alto, mismo ancho y mismas coordenadas. Si esto falla, cualquier
    cruce posterior devuelve basura.
    """
    import numpy as _np
    return (a.shape == b.shape
            and _np.allclose(a["x"].values, b["x"].values)
            and _np.allclose(a["y"].values, b["y"].values))


def inspeccionar(ds, nombre: str = "raster") -> None:
    """
    Lo que hay que mirar ANTES de operar sobre cualquier raster: CRS, tamano,
    bandas, nodata, dtype, extension, resolucion, pixeles validos, min y max.
    Saltarse este paso es donde se esconden los errores que despues no se
    explican.
    """
    import numpy as _np

    print(f"=== {nombre} ===")
    try:
        print(f"CRS          : {ds.odc.crs}")
    except Exception:
        print("CRS          : (no declarado por el accesor odc)")
    bandas = list(ds.data_vars) if hasattr(ds, "data_vars") else [ds.name]
    print(f"bandas       : {len(bandas)}  {bandas}")
    x, y = ds["x"].values, ds["y"].values
    rx = abs(float(x[1] - x[0])) if len(x) > 1 else float("nan")
    ry = abs(float(y[1] - y[0])) if len(y) > 1 else float("nan")
    print(f"ancho x alto : {len(x)} x {len(y)}  ({len(x) * len(y):,} pixeles)")
    print(f"resolucion   : {rx:.1f} x {ry:.1f} m")
    print(f"extension    : x [{x.min():,.0f}, {x.max():,.0f}]  "
          f"y [{y.min():,.0f}, {y.max():,.0f}]")
    for b in bandas:
        v = (ds[b] if hasattr(ds, "data_vars") else ds).values
        validos = _np.isfinite(v) if v.dtype.kind == "f" else _np.ones_like(v, bool)
        nv = int(validos.sum())
        print(f"  {b:5s} dtype {str(v.dtype):8s} nodata/NaN "
              f"{v.size - nv:,} ({1 - nv / v.size:.1%})  "
              f"validos {nv:,}" + (f"  min {v[validos].min():,.4g} "
                                   f"max {v[validos].max():,.4g}" if nv else ""))


def que_se_quemo(cobertura, mascara_quemado, resolucion: int = 20) -> pd.DataFrame:
    """Hectáreas quemadas por clase de cobertura."""
    ha_px = (resolucion ** 2) / 10_000
    cob = cobertura.values
    msk = mascara_quemado.values.astype(bool) & np.isfinite(cobertura.values)
    vals, cuentas = np.unique(cob[msk], return_counts=True)
    df = pd.DataFrame({
        "clase": [WORLDCOVER_CLASES.get(int(v), f"código {int(v)}") for v in vals],
        "hectareas": cuentas * ha_px,
    }).sort_values("hectareas", ascending=False).reset_index(drop=True)
    df["pct"] = df["hectareas"] / df["hectareas"].sum() * 100
    return df


# --------------------------------------------------------------------------
# 5 · WorldPop 2020 — a cuánta gente llegó
# --------------------------------------------------------------------------
URL_WORLDPOP = ("https://data.worldpop.org/GIS/Population/"
                "Global_2000_2020_1km_UNadj/2020/PER/"
                "per_ppp_2020_1km_Aggregated_UNadj.tif")


def worldpop() -> Path:
    """Raster de población del Perú, 1 km, 2020 (ajustado a ONU). ~8 MB."""
    return _bajar(URL_WORLDPOP, CACHE / "worldpop_peru_2020_1km.tif")


# --------------------------------------------------------------------------
# 6 · Google Open Buildings v3 — cuántas edificaciones
# --------------------------------------------------------------------------
OB_TILES = ("https://openbuildings-public-dot-gweb-research.uw.r.appspot.com"
            "/public/tiles.geojson")
OB_CSV = ("https://storage.googleapis.com/open-buildings-data/v3/"
          "polygons_s2_level_4_gzip_no_header/{cell}_buildings.csv.gz")
OB_COLUMNAS = ["latitude", "longitude", "area_in_meters", "confidence",
               "geometry", "full_plus_code"]


def open_buildings(area, confianza_min: float = 0.70) -> gpd.GeoDataFrame:
    """
    Edificaciones de Google Open Buildings v3 dentro de `area` (GeoDataFrame).
    Baja solo los tiles S2 que la tocan — pásale un distrito, no el país.
    """
    from shapely import wkt

    if isinstance(area, gpd.GeoSeries):
        area = gpd.GeoDataFrame(geometry=area, crs=area.crs)
    area = area.to_crs("EPSG:4326")
    union = area.union_all()
    minx, miny, maxx, maxy = union.bounds

    tiles = gpd.read_file(_bajar(OB_TILES, CACHE / "ob_tiles.geojson"))
    col = "tile_id" if "tile_id" in tiles.columns else tiles.columns[0]
    necesarios = tiles[tiles.intersects(union)][col].tolist()
    if not necesarios:
        raise RuntimeError("Ningún tile de Open Buildings cubre esa área.")

    partes = []
    for cell in necesarios:
        local = _bajar(OB_CSV.format(cell=cell), CACHE / f"ob_{cell}.csv.gz",
                       timeout=1800)
        with gzip.open(local, "rt") as f:
            for trozo in pd.read_csv(f, names=OB_COLUMNAS, chunksize=500_000):
                trozo = trozo[(trozo.confidence >= confianza_min)
                              & trozo.longitude.between(minx, maxx)
                              & trozo.latitude.between(miny, maxy)]
                if trozo.empty:
                    continue
                g = gpd.GeoDataFrame(
                    trozo.drop(columns=["geometry"]),
                    geometry=trozo["geometry"].apply(wkt.loads),
                    crs="EPSG:4326")
                partes.append(g[g.intersects(union)])

    if not partes:
        return gpd.GeoDataFrame(columns=OB_COLUMNAS, geometry=[], crs="EPSG:4326")
    return gpd.GeoDataFrame(pd.concat(partes, ignore_index=True),
                            geometry="geometry", crs="EPSG:4326")


# --------------------------------------------------------------------------
# 7 · Serie historica FIRMS 2012-2025 — ¿es 2026 un año excepcional?
# --------------------------------------------------------------------------
# El archivo de FIRMS se consulta por area y rango de fechas. La clave sale
# de .env (nunca se escribe en el codigo ni se sube a git).
FIRMS_AREA = ("https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
              "{key}/{src}/{area}/{dias}/{desde}")

# Mismo satelite (Suomi-NPP) en los dos casos; distinto procesamiento.
# NO son intercambiables en silencio: SP esta reprocesado y validado, NRT es
# de tiempo casi real. La comparacion historica lo dice explicitamente.
FIRMS_ARCHIVO = "VIIRS_SNPP_SP"    # 2012 -> hace ~3 meses
FIRMS_RECIENTE = "VIIRS_SNPP_NRT"  # ultimos meses

AREA_PERU = "-81.5,-18.5,-68.5,0"  # oeste,sur,este,norte


def map_key() -> str:
    """Lee FIRMS_MAP_KEY de .env o del entorno. Nunca la imprime."""
    import os

    clave = os.environ.get("FIRMS_MAP_KEY")
    if not clave:
        env = RAIZ / ".env"
        if env.exists():
            for linea in env.read_text(encoding="utf-8").splitlines():
                if linea.strip().startswith("FIRMS_MAP_KEY="):
                    clave = linea.split("=", 1)[1].strip()
                    break
    if not clave:
        raise RuntimeError(
            "Falta FIRMS_MAP_KEY. Copia .env.example como .env y pon tu clave "
            "(gratis en https://firms.modaps.eosdis.nasa.gov/api/map_key/).")
    return clave


def focos_ventana(desde: str, dias: int = 10, anio_reciente: int = 2026,
                  area: str = AREA_PERU) -> pd.DataFrame:
    """
    Focos en una ventana de hasta 10 dias (limite del servicio), para el
    Peru. `desde` en formato YYYY-MM-DD.

    Devuelve tambien la columna `procesamiento` (SP o NRT), para que la
    comparacion historica nunca mezcle sensores sin decirlo.
    """
    anio = int(desde[:4])
    src = FIRMS_RECIENTE if anio >= anio_reciente else FIRMS_ARCHIVO
    destino = CACHE / f"firms_area_{src}_{desde}_{dias}d.csv"

    if not destino.exists():
        url = FIRMS_AREA.format(key=map_key(), src=src, area=area,
                                dias=min(dias, 10), desde=desde)
        r = requests.get(url, timeout=300)
        r.raise_for_status()
        cuerpo = r.text
        if len(cuerpo) < 60 or "latitude" not in cuerpo[:200].lower():
            raise RuntimeError(f"FIRMS devolvio algo inesperado: {cuerpo[:200]}")
        destino.write_text(cuerpo, encoding="utf-8")

    df = pd.read_csv(destino)
    df.columns = [c.lower() for c in df.columns]
    df["procesamiento"] = "NRT" if src.endswith("NRT") else "SP"
    df["anio"] = anio
    return df


def serie_historica(mes: int, dia: int, dias: int = 10,
                    anios=range(2012, 2027),
                    confianza_minima: str = "n") -> pd.DataFrame:
    """
    La MISMA ventana calendario en cada año: del `dia`/`mes` a `dias` dias
    despues, para cada año de `anios`. Esa es la unica comparacion honesta —
    un 2026 incompleto nunca se compara contra años completos.

    Devuelve un GeoDataFrame con el año y el departamento de cada foco.
    """
    partes = []
    for anio in anios:
        desde = f"{anio}-{mes:02d}-{dia:02d}"
        try:
            partes.append(focos_ventana(desde, dias))
        except Exception as e:
            print(f"  {anio}: sin datos ({type(e).__name__}) — se excluye, "
                  f"no se rellena")
    if not partes:
        raise RuntimeError("Ningun año devolvio datos")

    df = pd.concat(partes, ignore_index=True)
    if "confidence" in df and confianza_minima == "n":
        conf = df["confidence"].astype(str).str.strip().str.lower()
        df = df[conf.str[0].isin(["n", "h"])]

    gdf = gpd.GeoDataFrame(
        df.reset_index(drop=True),
        geometry=gpd.points_from_xy(df.longitude, df.latitude),
        crs="EPSG:4326")

    dep = distritos()[["departamento", "geometry"]]
    return gpd.sjoin(gdf, dep, how="inner", predicate="within").drop(
        columns="index_right")


def anomalia_departamental(serie: gpd.GeoDataFrame,
                           anio_foco: int = 2026) -> pd.DataFrame:
    """
    Por departamento: focos del año en curso frente a su propia historia.
    Incluye z-score y el puesto que ocupa el año en su serie, porque un
    porcentaje solo no dice si el salto es raro para ESE departamento.
    """
    conteo = (serie.groupby(["departamento", "anio"]).size()
                   .rename("focos").reset_index())

    hist = conteo[conteo.anio < anio_foco]
    actual = (conteo[conteo.anio == anio_foco]
              .set_index("departamento")["focos"])

    res = (hist.groupby("departamento")["focos"]
               .agg(promedio="mean", mediana="median", maximo="max",
                    desvio="std", anios="size")
               .reset_index())
    res["focos_" + str(anio_foco)] = res["departamento"].map(actual).fillna(0)

    act = res[f"focos_{anio_foco}"]
    res["diferencia"] = act - res["promedio"]
    res["variacion_pct"] = (act / res["promedio"].replace(0, np.nan) - 1) * 100
    res["z"] = (act - res["promedio"]) / res["desvio"].replace(0, np.nan)

    # puesto de este año dentro de su propia serie (1 = el mas alto)
    puestos = []
    for _, f in res.iterrows():
        serie_dep = hist[hist.departamento == f.departamento]["focos"].tolist()
        serie_dep.append(f[f"focos_{anio_foco}"])
        orden = sorted(serie_dep, reverse=True)
        puestos.append(orden.index(f[f"focos_{anio_foco}"]) + 1)
    res["puesto_en_su_serie"] = puestos
    res["de_n_anios"] = res["anios"] + 1

    return res.sort_values("diferencia", ascending=False).reset_index(drop=True)
