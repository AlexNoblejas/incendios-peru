"""
Exporta outputs/escena3d.json: el terreno del AOI con sus texturas, para la
vista 3D del tablero.

Incluye, sobre una misma grilla:
  - altitud (Copernicus DEM GLO-30)
  - color natural y falso color infrarrojo (Sentinel-2 L2A)
  - severidad dNBR
  - los focos VIIRS con su altitud, hora y FRP

Todo se remuestrea a una malla chica (<=140 px por lado) para que quepa en el
HTML; las cifras del analisis NO salen de aca, salen del notebook.
"""
import json, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import geopandas as gpd
import numpy as np
import pandas as pd
import datos

MALLA = 140          # lado maximo de la malla 3D
SALIDA = RAIZ / "outputs" / "escena3d.json"
H = json.loads((RAIZ / "outputs" / "hallazgos.json").read_text(encoding="utf-8"))

FECHA_ANTES = H["imagenes"]["antes"]["fecha"]
FECHA_DESPUES = H["imagenes"]["despues"]["fecha"]
UMBRAL = H["area_quemada"]["umbral_dnbr"]
RES = H["imagenes"]["resolucion_m"]

# ---- el mismo incendio que el notebook -------------------------------------
focos = datos.focos_7d("viirs-snpp", confianza_minima="n")
zona = datos.distrito("MANANTAY", "UCAYALI")
fz = gpd.sjoin(focos, zona[["geometry"]], predicate="within").drop(
    columns="index_right")
agr = datos.agrupar_incendios(fz, 1.0, 48.0)
inc = datos.resumen_incendios(agr, 375)
EVENTO = inc.sort_values("frp_total", ascending=False).iloc[0]

aoi_m = gpd.GeoDataFrame(geometry=[EVENTO.geometry.buffer(2000)],
                         crs=datos.CRS_METRICO)
BBOX = tuple(aoi_m.to_crs(4326).total_bounds)
print(f"AOI {aoi_m.area.iloc[0]/1e4:,.0f} ha")


def una_escena(fecha):
    """La escena Sentinel-2 de esa fecha, con las bandas para RGB y NBR."""
    import odc.stac
    items = datos.buscar_sentinel2(BBOX, fecha, fecha, nubes_max=100)
    if not items:
        d = pd.Timestamp(fecha)
        items = datos.buscar_sentinel2(
            BBOX, str((d - pd.Timedelta(days=1)).date()),
            str((d + pd.Timedelta(days=1)).date()), nubes_max=100)
    it = items[0]
    ds = odc.stac.load([it], bands=["B02", "B03", "B04", "B08", "B12", "SCL"],
                       bbox=BBOX, crs=datos.CRS_METRICO, resolution=RES,
                       chunks={}).isel(time=0).compute()
    return ds


print("leyendo Sentinel-2...")
ds_a = una_escena(FECHA_ANTES)
ds_d = una_escena(FECHA_DESPUES)
dnbr = datos.nbr(ds_a) - datos.nbr(ds_d)

# ---- relieve ---------------------------------------------------------------
print("leyendo Copernicus DEM GLO-30...")
import odc.stac
items_dem = list(datos.catalogo().search(
    collections=["cop-dem-glo-30"], bbox=BBOX).items())
dem = odc.stac.load(items_dem, bands=["data"], like=ds_d,
                    resampling="bilinear", chunks={})
dem = (dem.isel(time=0) if "time" in dem.dims else dem)["data"].compute()
datos.inspeccionar(dem.to_dataset(name="altitud"), "Copernicus DEM GLO-30")

assert datos.misma_grilla(dem, dnbr), "el DEM no quedo en la grilla del dNBR"
print("DEM en la misma grilla que el dNBR")


def reducir(a, paso):
    return np.asarray(a)[::paso, ::paso]


alto, ancho = dem.shape
paso = max(1, int(np.ceil(max(alto, ancho) / MALLA)))
print(f"malla: {alto}x{ancho} -> paso {paso} -> "
      f"{len(range(0, alto, paso))}x{len(range(0, ancho, paso))}")

z = reducir(dem.values, paso).astype("float32")
z = np.nan_to_num(z, nan=float(np.nanmedian(z)))


def rgb(ds, bandas, pmin=2, pmax=98):
    """Composicion de tres bandas estirada por percentiles, a 0-255."""
    capas = []
    for b in bandas:
        v = reducir(ds[b].values, paso).astype("float32")
        lo, hi = np.nanpercentile(v, pmin), np.nanpercentile(v, pmax)
        capas.append(np.clip((v - lo) / max(hi - lo, 1e-6), 0, 1))
    return (np.stack(capas, -1) * 255).astype("uint8")


natural = rgb(ds_d, ["B04", "B03", "B02"])           # color natural
infrarrojo = rgb(ds_d, ["B08", "B04", "B03"])        # vegetacion en rojo
d_small = reducir(dnbr.values, paso)

# severidad -> color (las mismas clases del notebook)
cortes = [0.10, UMBRAL, 0.44, 0.66]
paleta = np.array([[60, 62, 68], [255, 217, 160], [255, 157, 77],
                   [224, 34, 0], [140, 12, 0]], dtype="uint8")
idx = np.zeros(d_small.shape, dtype=int)
for i, c in enumerate(cortes):
    idx[np.nan_to_num(d_small, nan=-9) >= c] = i + 1
severidad = paleta[idx]
severidad[~np.isfinite(d_small)] = [90, 92, 98]      # sin dato por nube

# ---- focos con su altitud --------------------------------------------------
xs, ys = dem["x"].values, dem["y"].values
focos_m = datos.a_metros(agr)
puntos = []
for _, p in focos_m.iterrows():
    j = int(np.argmin(np.abs(xs - p.geometry.x)))
    i = int(np.argmin(np.abs(ys - p.geometry.y)))
    if not (0 <= i < alto and 0 <= j < ancho):
        continue
    puntos.append({"u": round(j / (ancho - 1), 4), "v": round(i / (alto - 1), 4),
                   "z": round(float(dem.values[i, j]), 1),
                   "f": round(float(p.frp), 1),
                   "d": p.momento.strftime("%d-%b %H:%M")})

alt = np.array([p["z"] for p in puntos]) if puntos else np.array([0.0])

# pendiente mediana, en grados
gy, gx = np.gradient(dem.values.astype("float32"), RES, RES)
pend = np.degrees(np.arctan(np.hypot(gx, gy)))

# ---- series por dia --------------------------------------------------------
agr["dia"] = agr["momento"].dt.strftime("%d-%b")
por_dia = (agr.groupby("dia", sort=False)
              .agg(focos=("frp", "size"), frp=("frp", "sum"))
              .reset_index())
orden = agr.groupby("dia", sort=False)["momento"].min().sort_values().index
por_dia = por_dia.set_index("dia").loc[orden].reset_index()
# huella acumulada: buffer de 375 m de los focos hasta cada dia
acum = []
hasta = None
for d in por_dia["dia"]:
    sel = agr[agr["momento"] <= agr.loc[agr.dia == d, "momento"].max()]
    hasta = datos.a_metros(sel).buffer(375).union_all()
    acum.append(round(hasta.area / 1e4, 1))
por_dia["huella_acum_ha"] = acum
por_dia["huella_nueva_ha"] = por_dia["huella_acum_ha"].diff().fillna(
    por_dia["huella_acum_ha"]).round(1)

escena = {
    "malla": {"ancho": int(z.shape[1]), "alto": int(z.shape[0]),
              "z": [round(float(v), 1) for v in z.ravel()],
              "zmin": round(float(z.min()), 1), "zmax": round(float(z.max()), 1),
              "metros_x": round(float(abs(xs[-1] - xs[0])), 1),
              "metros_y": round(float(abs(ys[-1] - ys[0])), 1)},
    "texturas": {
        "natural": natural.ravel().tolist(),
        "infrarrojo": infrarrojo.ravel().tolist(),
        "severidad": severidad.ravel().tolist(),
    },
    "focos": puntos,
    "metricas": {
        "altitud_min": round(float(alt.min()), 1),
        "altitud_max": round(float(alt.max()), 1),
        "altitud_mediana": round(float(np.median(alt)), 1),
        "pendiente_mediana": round(float(np.nanmedian(pend)), 1),
        "fecha_imagen": FECHA_DESPUES,
        "umbral": UMBRAL,
    },
    "por_dia": json.loads(por_dia.to_json(orient="records")),
    "histograma_altitud": {},
}

if len(alt) > 1:
    lo = int(np.floor(alt.min() / 10) * 10)
    hi = int(np.ceil(alt.max() / 10) * 10) + 10
    bordes = list(range(lo, hi + 1, 10))
    cuenta, _ = np.histogram(alt, bins=bordes)
    escena["histograma_altitud"] = {
        "bordes": bordes, "cuenta": [int(c) for c in cuenta]}

SALIDA.write_text(json.dumps(escena, ensure_ascii=False), encoding="utf-8")
print(f"{SALIDA.name}: {SALIDA.stat().st_size/1e6:.1f} MB · "
      f"malla {z.shape[1]}x{z.shape[0]} · {len(puntos)} focos")
print(f"altitud {escena['metricas']['altitud_min']}-"
      f"{escena['metricas']['altitud_max']} m · pendiente mediana "
      f"{escena['metricas']['pendiente_mediana']}°")
print(por_dia.to_string(index=False))
