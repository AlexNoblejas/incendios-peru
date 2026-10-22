"""Genera notebooks/incendios_manantay.ipynb."""
import json
from pathlib import Path

C = []


def md(t):
    C.append({"cell_type": "markdown", "metadata": {},
              "source": t.strip("\n").splitlines(keepends=True)})


def code(t):
    C.append({"cell_type": "code", "metadata": {}, "execution_count": None,
              "outputs": [], "source": t.strip("\n").splitlines(keepends=True)})


md(r"""
# ¿Cuánto se quemó en Manantay, qué se quemó y a quién llegó?

**Ciencia de Datos con Python · 21 de octubre de 2026 · Alexander Noblejas**

Manantay es uno de los cuatro distritos de Pucallpa, en Coronel Portillo, Ucayali.
Es un distrito periurbano: ciudad por el norte, chacra y bosque secundario por el sur.
Esa mezcla es justamente lo que hace interesante la pregunta, porque el fuego en
Manantay no cae sobre territorio vacío.

La tarea pide elegir una pregunta. Esta junta tres de los retos propuestos:

| Reto | Pregunta | Qué responde acá |
|---|---|---|
| **A** | ¿Cuánto se quemó? | dNBR con Sentinel-2, hectáreas por severidad |
| **C** | ¿Qué se quemó? | cruce con ESA WorldCover: bosque, pastizal, cultivo |
| **D** | ¿A quién afectó? | WorldPop a 5 km + **Google Open Buildings** a 1 km |

La tercera es la que agrega algo al ejemplo de clase: WorldPop dice *cuánta gente*
en celdas de 1 km, pero no *cuántas casas*. Open Buildings sí: son polígonos de
edificación detectados sobre imagen satelital, uno por techo. A escala de un incendio
periurbano, esa diferencia de resolución es la diferencia entre "unos miles de
personas en la zona" y "estas 340 construcciones quedaron a menos de un kilómetro".

> **La advertencia del profesor, asumida desde el principio:** la computadora siempre
> da un número. Todas las decisiones de método —fechas, nubes, umbral de dNBR, radio
> de los buffers— están explícitas en el notebook y reportadas en el README.
""")

md(r"""
## 0 · Preparación

```bash
pip install geopandas rasterio rasterstats shapely folium mapclassify \
            pystac-client planetary-computer odc-stac rioxarray scikit-learn requests
```

Todo corre en CPU. Las descargas se cachean en `data/`, así que la segunda corrida
es rápida.
""")

code(r"""
import sys, warnings, json
from pathlib import Path

sys.path.append(str(Path.cwd().parent / "src"))

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import datos   # src/datos.py — todas las fuentes, ninguna con clave

warnings.filterwarnings("ignore")
pd.set_option("display.float_format", lambda v: f"{v:,.2f}")
plt.rcParams.update({"figure.dpi": 110, "font.size": 9,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.25})

RESOLUCION = 20          # m por píxel para todo el análisis raster
UMBRAL_QUEMADO = 0.27    # dNBR: desde "moderada-baja" (Key & Benson)
RADIO_VIVIENDAS_M = 1000
RADIO_POBLACION_M = 5000
""")

md(r"""
## 1 · Dónde arde el país esta semana

Antes del zoom, el contexto. FIRMS publica cada día un CSV con todos los focos de
calor de Sudamérica de los últimos 7 días. Es descarga directa: no pide clave.

Un **foco de calor** no es un incendio: es un píxel donde el satélite midió una
anomalía térmica. Puede ser un incendio forestal, una quema agrícola controlada, un
horno ladrillero o una antorcha de gas. Esa ambigüedad no se resuelve con código —
se declara.
""")

code(r"""
focos = datos.focos_7d("viirs-snpp", confianza_minima="n")

print(f"{len(focos):,} focos VIIRS en el Perú")
print(f"ventana: {focos.momento.min():%d-%b %H:%M} a {focos.momento.max():%d-%b-%Y %H:%M} UTC")
focos[["latitude", "longitude", "momento", "confidence", "frp"]].head()
""")

code(r"""
dist = datos.distritos()
assert dist.crs == focos.crs, "CRS distintos: reproyectar antes de cruzar"

cruce = gpd.sjoin(focos, dist[["departamento", "provincia", "distrito", "geometry"]],
                  how="inner", predicate="within")

por_depa = (cruce.groupby("departamento")
                 .agg(focos=("frp", "size"), frp=("frp", "sum"))
                 .sort_values("focos", ascending=False))

fig, ax = plt.subplots(figsize=(7.5, 4))
top12 = por_depa.head(12)
ax.barh(top12.index[::-1], top12.focos[::-1], color="#c1440e")
ax.set_xlabel("focos de calor (7 días)")
ax.set_title("Dónde arde el Perú esta semana", fontsize=10)
plt.tight_layout(); plt.show()

print(por_depa.head(8).to_string())
""")

code(r"""
por_dist = (cruce.groupby(["departamento", "provincia", "distrito"])
                 .agg(focos=("frp", "size"), frp_total=("frp", "sum"))
                 .sort_values("frp_total", ascending=False)
                 .reset_index())

print("TOP 15 distritos por energía liberada (FRP acumulado)")
print(por_dist.head(15).to_string(index=False))

pos = por_dist.index[por_dist.distrito == "MANANTAY"]
print(f"\nManantay: puesto {int(pos[0]) + 1} de {len(por_dist)} distritos con fuego"
      if len(pos) else "\nManantay no registra focos en esta ventana de 7 días")
""")

md(r"""
## 2 · Del foco al incendio

Un incendio grande produce decenas de focos repartidos en el tiempo. Para contar
*incendios* y no *detecciones* hay que agruparlos. La regla que usamos es la del
ejemplo de clase, y es una decisión más: **dos focos son el mismo incendio si están
a menos de 1 km y a menos de 48 horas**.

Implementado como DBSCAN sobre tres ejes —x, y, y el tiempo convertido a metros—
de modo que una sola distancia gobierna el espacio y el tiempo a la vez.
""")

code(r"""
zona = datos.distrito("MANANTAY", "UCAYALI")
print(f"Manantay · {zona.iloc[0]['provincia']}, {zona.iloc[0]['departamento']} · "
      f"UBIGEO {zona.iloc[0]['ubigeo']}")
print(f"superficie: {datos.a_metros(zona).area.iloc[0] / 1e6:,.0f} km²")

focos_zona = gpd.sjoin(focos, zona[["geometry"]], predicate="within").drop(
    columns="index_right")
print(f"\nfocos dentro del distrito, últimos 7 días: {len(focos_zona)}")
""")

code(r"""
agrupados = datos.agrupar_incendios(focos_zona, radio_km=1.0, horas=48.0)
incendios = datos.resumen_incendios(agrupados, buffer_m=375)

print(f"{len(incendios)} incendios distintos a partir de {len(agrupados)} focos\n")
print(incendios[["incendio_id", "n_focos", "frp_total", "frp_max",
                 "inicio", "fin", "horas", "huella_ha"]].head(10).to_string(index=False))
""")

md(r"""
La columna `huella_ha` es solo el buffer de 375 m alrededor de cada foco —el tamaño
del píxel VIIRS— unido. Es una cota, no una medición: sobreestima los fuegos
puntuales y subestima los grandes. La medición de verdad viene del raster.
""")

# ---------------------------------------------------------------- 3
md(r"""
## 3 · El incendio elegido y su ventana temporal

Tomamos el incendio con más energía liberada y definimos el área de interés con un
margen de 2 km alrededor. Las fechas salen del propio incendio: la imagen **antes**
debe ser anterior al primer foco, la de **después**, posterior al último.
""")

code(r"""
from shapely.geometry import box

EVENTO = incendios.iloc[0]
print(f"incendio #{EVENTO.incendio_id}: {EVENTO.n_focos} focos, "
      f"FRP {EVENTO.frp_total:,.0f} MW")
print(f"activo del {EVENTO.inicio:%d-%b %H:%M} al {EVENTO.fin:%d-%b %H:%M} UTC "
      f"({EVENTO.horas:.0f} h)")

MARGEN_M = 2000
aoi_m = gpd.GeoDataFrame(geometry=[EVENTO.geometry.buffer(MARGEN_M)],
                         crs=datos.CRS_METRICO)
BBOX = tuple(aoi_m.to_crs(4326).total_bounds)
print(f"\nárea de interés: {aoi_m.area.iloc[0] / 1e4:,.0f} ha")
print(f"bbox: {[round(v, 4) for v in BBOX]}")

INICIO_FUEGO = EVENTO.inicio.date()
FIN_FUEGO = EVENTO.fin.date()
""")

md(r"""
## 4 · Las imágenes: fechas y nubes, antes de calcular nada

Este es el paso que el profesor pidió mirar primero. Sentinel-2 pasa cada 5 días,
pero **la nube manda**: en la selva de Ucayali, en octubre, la mayoría de escenas son
inservibles. Listamos todas las candidatas con su fecha y su nubosidad antes de
elegir.

Ojo: `eo:cloud_cover` es la nubosidad de **la escena completa** (110 × 110 km). Lo
que importa es la nubosidad **sobre nuestro recorte**, que calculamos después con la
capa SCL. Pueden ser muy distintas.
""")

code(r"""
candidatas_antes = datos.buscar_sentinel2(
    BBOX, str(INICIO_FUEGO - pd.Timedelta(days=45)), str(INICIO_FUEGO), nubes_max=95)
candidatas_despues = datos.buscar_sentinel2(
    BBOX, str(FIN_FUEGO), str(FIN_FUEGO + pd.Timedelta(days=20)), nubes_max=95)

print("CANDIDATAS ANTES DEL FUEGO")
print(datos.tabla_escenas(candidatas_antes).tail(10).to_string(index=False))
print("\nCANDIDATAS DESPUÉS DEL FUEGO")
print(datos.tabla_escenas(candidatas_despues).head(10).to_string(index=False))
""")

code(r"""
def mejor_escena(items, etiqueta):
    'Elige la escena con menos nubes SOBRE EL RECORTE, no sobre la escena.'
    mejor, mejor_pct, mejor_ds = None, 101.0, None
    for it in items[-8:] if etiqueta == "antes" else items[:8]:
        try:
            ds = datos.leer_bandas(it, BBOX, RESOLUCION)
        except Exception as e:
            print(f"  {it.datetime.date()} — no se pudo leer ({type(e).__name__})")
            continue
        pct = datos.pct_nubes(ds)
        print(f"  {it.datetime.date()} — nubes sobre el recorte: {pct:5.1f}%")
        if pct < mejor_pct:
            mejor, mejor_pct, mejor_ds = it, pct, ds
    if mejor is None:
        raise RuntimeError(f"Ninguna escena {etiqueta} se pudo leer")
    print(f"→ elegida {etiqueta}: {mejor.datetime.date()} ({mejor_pct:.1f}% nubes)\n")
    return mejor, mejor_pct, mejor_ds

print("ANTES:")
it_antes, nubes_antes, ds_antes = mejor_escena(candidatas_antes, "antes")
print("DESPUÉS:")
it_despues, nubes_despues, ds_despues = mejor_escena(candidatas_despues, "después")

FECHA_ANTES = it_antes.datetime.date()
FECHA_DESPUES = it_despues.datetime.date()
""")

md(r"""
**Esto es lo que hay que reportar siempre**, y es el único motivo por el que el
número final es creíble o no: qué dos fechas, cuántos días de separación, y qué
porcentaje del recorte estaba tapado por nubes en cada una.
""")

# ---------------------------------------------------------------- 5
md(r"""
## 5 · NBR y dNBR

El **Normalized Burn Ratio** contrasta el infrarrojo cercano (B08), que la vegetación
sana refleja mucho, con el infrarrojo de onda corta (B12), que el suelo quemado y seco
refleja mucho:

$$\text{NBR} = \frac{\text{B08} - \text{B12}}{\text{B08} + \text{B12}}$$

Vegetación sana: NBR alto. Superficie quemada: NBR bajo o negativo. La diferencia
entre antes y después aísla el cambio:

$$\text{dNBR} = \text{NBR}_{\text{antes}} - \text{NBR}_{\text{después}}$$

Los píxeles tapados por nube en *cualquiera* de las dos fechas quedan fuera: la
máscara SCL se propaga sola al restar, porque `NaN - x = NaN`.
""")

code(r"""
nbr_antes = datos.nbr(ds_antes)
nbr_despues = datos.nbr(ds_despues)
dnbr = nbr_antes - nbr_despues

validos = np.isfinite(dnbr.values)
print(f"píxeles utilizables: {validos.sum():,} de {dnbr.size:,} "
      f"({validos.mean():.1%}) — el resto quedó bajo nube en alguna de las dos fechas")
print(f"dNBR  mediana {np.nanmedian(dnbr.values):+.3f} · "
      f"p99 {np.nanpercentile(dnbr.values, 99):+.3f} · "
      f"máx {np.nanmax(dnbr.values):+.3f}")
""")

code(r"""
fig, axes = plt.subplots(1, 3, figsize=(13, 4.6))

for ax, capa, titulo, cmap, lim in [
    (axes[0], nbr_antes,  f"NBR antes · {FECHA_ANTES}",   "RdYlGn", (-0.5, 0.9)),
    (axes[1], nbr_despues, f"NBR después · {FECHA_DESPUES}", "RdYlGn", (-0.5, 0.9)),
    (axes[2], dnbr,        "dNBR (antes − después)",       "inferno", (-0.2, 0.9)),
]:
    im = ax.imshow(capa.values, cmap=cmap, vmin=lim[0], vmax=lim[1])
    ax.set_title(titulo, fontsize=9)
    ax.axis("off")
    fig.colorbar(im, ax=ax, fraction=0.045)

fig.suptitle("El fuego visto por Sentinel-2 · gris = nube enmascarada", fontsize=10.5)
plt.tight_layout(); plt.show()
""")

# ---------------------------------------------------------------- 6
md(r"""
## 6 · Hectáreas quemadas · el número depende del umbral

Los umbrales de severidad son los de Key & Benson (USGS), estándar en la literatura.
Pero **la frontera entre "quemado" y "no quemado" es una decisión nuestra**: acá
tomamos dNBR ≥ 0.27 (desde severidad moderada-baja). Con 0.10 el número sube mucho y
mete ruido de sequía; con 0.44 baja y pierde el borde real del fuego.

Por eso, además de nuestro número, mostramos qué pasa con los otros umbrales. Es
exactamente la tabla que el profesor mostró para Curahuasi.
""")

code(r"""
sev = datos.hectareas_por_severidad(dnbr, RESOLUCION)
print(sev.to_string(index=False))

ha_quemadas = sev.loc[sev.dnbr_min >= UMBRAL_QUEMADO, "hectareas"].sum()
print(f"\nÁREA QUEMADA (dNBR ≥ {UMBRAL_QUEMADO}): {ha_quemadas:,.0f} ha")
""")

code(r"""
print("La misma imagen, cuatro umbrales:\n")
sensibilidad = []
for u in [0.10, 0.27, 0.44, 0.66]:
    ha = float((dnbr.values >= u).sum()) * (RESOLUCION ** 2) / 1e4
    sensibilidad.append({"umbral dNBR": u, "hectáreas": ha})
sens = pd.DataFrame(sensibilidad)
print(sens.to_string(index=False))
print("\nReportamos el de 0.27. Los otros tres son el intervalo de lo defendible.")
""")

code(r"""
quemado = dnbr >= UMBRAL_QUEMADO

fig, ax = plt.subplots(figsize=(7, 6.4))
ax.imshow(np.where(np.isfinite(dnbr.values), dnbr.values, np.nan),
          cmap="Greys", vmin=-0.3, vmax=0.3)
ax.imshow(np.where(quemado.values, 1, np.nan), cmap="autumn_r", alpha=0.85)
ax.set_title(f"Superficie quemada · {ha_quemadas:,.0f} ha  (dNBR ≥ {UMBRAL_QUEMADO})\n"
             f"{FECHA_ANTES} → {FECHA_DESPUES}", fontsize=9.5)
ax.axis("off")
plt.tight_layout(); plt.show()
""")

# ---------------------------------------------------------------- 7
md(r"""
## 7 · ¿Qué se quemó?

Ahora el cruce del reto C. ESA WorldCover clasifica el planeta entero a 10 m en once
clases. Lo leemos sobre la misma área, a la misma resolución y en el mismo CRS que el
dNBR —si no coincidieran, el cruce devolvería basura— y contamos hectáreas quemadas
por clase de cobertura.
""")

code(r"""
cobertura = datos.worldcover(BBOX, RESOLUCION)
cobertura = cobertura.rio.reproject_match(dnbr) if hasattr(cobertura, "rio") else cobertura

tabla_cob = datos.que_se_quemo(cobertura, quemado, RESOLUCION)
print(tabla_cob.to_string(index=False))
""")

code(r"""
fig, ax = plt.subplots(figsize=(7, 3.8))
t = tabla_cob.head(6)
ax.barh(t["clase"][::-1], t["hectareas"][::-1], color="#8c2f0d")
for i, (ha, pct) in enumerate(zip(t.hectareas[::-1], t.pct[::-1])):
    ax.text(ha, i, f"  {ha:,.0f} ha ({pct:.0f}%)", va="center", fontsize=8)
ax.set_xlabel("hectáreas quemadas")
ax.set_title("Qué se quemó, según ESA WorldCover 2021", fontsize=10)
plt.tight_layout(); plt.show()
""")

md(r"""
WorldCover es de 2021 y el fuego es de 2026: si en el medio hubo deforestación o
cambio de uso, la clase asignada está desactualizada. En un distrito periurbano con
frente agrícola activo, ese desfase de cinco años no es menor y va en una dirección
conocida —subestima lo construido y lo agrícola, sobreestima el bosque—.
""")

# ---------------------------------------------------------------- 8
md(r"""
## 8 · ¿A quién llegó?

Dos medidas de exposición, a dos escalas distintas.

**WorldPop (1 km)** da personas por celda: sirve para el orden de magnitud a 5 km.
**Google Open Buildings (polígono por techo)** da edificaciones: sirve para decir
cuántas construcciones quedaron realmente al borde del fuego. La primera es la que
sugiere la tarea; la segunda es lo que agregamos.
""")

code(r"""
from rasterstats import zonal_stats

anillo_pob = gpd.GeoDataFrame(
    geometry=[EVENTO.geometry.buffer(RADIO_POBLACION_M)], crs=datos.CRS_METRICO)

pob = zonal_stats(anillo_pob.to_crs(4326), str(datos.worldpop()),
                  stats=["sum"], nodata=-99999, all_touched=True)[0]["sum"]

print(f"población a {RADIO_POBLACION_M/1000:.0f} km del incendio "
      f"(WorldPop 2020, 1 km): {pob:,.0f} personas")
""")

code(r"""
edificios = datos.open_buildings(aoi_m.to_crs(4326), confianza_min=0.70)
print(f"{len(edificios):,} edificaciones en el área de interés")

ed_m = datos.a_metros(edificios)
anillo_viv = EVENTO.geometry.buffer(RADIO_VIVIENDAS_M)

cerca = ed_m[ed_m.intersects(anillo_viv)]
print(f"a menos de {RADIO_VIVIENDAS_M} m del incendio: {len(cerca):,} edificaciones")
print(f"superficie construida expuesta: {cerca.area_in_meters.sum()/1e4:,.1f} ha")
print(f"tamaño mediano: {cerca.area_in_meters.median():,.0f} m² "
      f"(coherente con vivienda unifamiliar si está entre 40 y 150)")
""")

code(r"""
fig, ax = plt.subplots(figsize=(8, 8))

datos.a_metros(zona).boundary.plot(ax=ax, color="#999", linewidth=0.8)
gpd.GeoSeries([anillo_viv], crs=datos.CRS_METRICO).plot(
    ax=ax, facecolor="none", edgecolor="#c1440e", linestyle="--", linewidth=1.1)
gpd.GeoSeries([EVENTO.geometry], crs=datos.CRS_METRICO).plot(
    ax=ax, color="#c1440e", alpha=0.3)
ed_m.plot(ax=ax, color="#c8ccd4", markersize=0.5, linewidth=0)
cerca.plot(ax=ax, color="#1d3557", markersize=1.5, linewidth=0)
datos.a_metros(agrupados).plot(ax=ax, color="#ff2d00", markersize=10, marker="x")

minx, miny, maxx, maxy = aoi_m.total_bounds
ax.set_xlim(minx, maxx); ax.set_ylim(miny, maxy)
ax.set_title(f"Manantay · {len(cerca):,} edificaciones a menos de "
             f"{RADIO_VIVIENDAS_M} m del fuego\n"
             "rojo: focos VIIRS · azul: edificaciones expuestas "
             "(Google Open Buildings v3)", fontsize=9.5)
ax.set_axis_off()
plt.tight_layout(); plt.show()
""")

# ---------------------------------------------------------------- 9
md(r"""
## 9 · El mapa
""")

code(r"""
import folium

m = folium.Map(location=[EVENTO.lat, EVENTO.lon], zoom_start=12,
               tiles="CartoDB positron")
folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/"
          "World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Esri", name="Satélite").add_to(m)

folium.GeoJson(zona.to_json(), name="Manantay",
               style_function=lambda f: {"color": "#444", "weight": 1.5,
                                         "fillOpacity": 0}).add_to(m)

folium.GeoJson(
    gpd.GeoDataFrame(geometry=[anillo_viv], crs=datos.CRS_METRICO)
       .to_crs(4326).to_json(),
    name=f"Anillo {RADIO_VIVIENDAS_M} m",
    style_function=lambda f: {"color": "#c1440e", "weight": 1.5,
                              "dashArray": "6", "fillOpacity": 0.05}).add_to(m)

for _, r in agrupados.iterrows():
    folium.CircleMarker(
        [r.latitude, r.longitude], radius=4, color="#ff2d00",
        fill=True, fill_opacity=0.85,
        popup=f"{r.momento:%d-%b %H:%M} UTC · FRP {r.frp:.1f} MW").add_to(m)

folium.LayerControl().add_to(m)
m.save("../outputs/mapa_manantay.html")
m
""")

# ---------------------------------------------------------------- 10
md(r"""
## 10 · Exportar los hallazgos

Un JSON con todo lo que el tablero y el README necesitan — sin cifras escritas a
mano en ningún lado.
""")

code(r"""
hallazgos = {
    "distrito": "Manantay",
    "provincia": "Coronel Portillo",
    "departamento": "Ucayali",
    "ubigeo": str(zona.iloc[0]["ubigeo"]),
    "corte": pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    "focos": {
        "sensor": "VIIRS S-NPP (FIRMS, 7 días)",
        "ventana": [str(focos.momento.min()), str(focos.momento.max())],
        "en_distrito": int(len(focos_zona)),
        "incendios_detectados": int(len(incendios)),
    },
    "incendio": {
        "id": int(EVENTO.incendio_id),
        "n_focos": int(EVENTO.n_focos),
        "frp_total_mw": round(float(EVENTO.frp_total), 1),
        "inicio": str(EVENTO.inicio), "fin": str(EVENTO.fin),
        "horas_activo": round(float(EVENTO.horas), 1),
    },
    "imagenes": {
        "antes": {"fecha": str(FECHA_ANTES), "nubes_recorte_pct": round(nubes_antes, 1)},
        "despues": {"fecha": str(FECHA_DESPUES), "nubes_recorte_pct": round(nubes_despues, 1)},
        "dias_entre": (FECHA_DESPUES - FECHA_ANTES).days,
        "pixeles_utilizables_pct": round(float(validos.mean() * 100), 1),
    },
    "area_quemada": {
        "umbral_dnbr": UMBRAL_QUEMADO,
        "hectareas": round(float(ha_quemadas), 1),
        "por_severidad": sev.to_dict("records"),
        "sensibilidad_umbral": sens.to_dict("records"),
    },
    "que_se_quemo": tabla_cob.to_dict("records"),
    "exposicion": {
        "poblacion_5km_worldpop2020": int(pob),
        "edificaciones_1km_openbuildings": int(len(cerca)),
        "ha_construidas_1km": round(float(cerca.area_in_meters.sum() / 1e4), 2),
        "edificaciones_aoi": int(len(edificios)),
    },
}

Path("../outputs").mkdir(exist_ok=True)
Path("../outputs/hallazgos.json").write_text(
    json.dumps(hallazgos, indent=2, ensure_ascii=False), encoding="utf-8")

sev.to_csv("../outputs/severidad.csv", index=False)
tabla_cob.to_csv("../outputs/cobertura_quemada.csv", index=False)
por_dist.head(50).to_csv("../outputs/ranking_distrital_7d.csv", index=False)

print(json.dumps(hallazgos, indent=2, ensure_ascii=False)[:1800])
""")

# ---------------------------------------------------------------- 11
md(r"""
## 11 · Limitaciones

Las cinco que condicionan cada número de arriba:

1. **Un foco de calor no es un incendio.** VIIRS detecta anomalías térmicas: quemas
   agrícolas controladas, hornos ladrilleros y fuegos forestales entran al mismo
   conteo. Separarlos requiere información de campo que no tenemos.
2. **Las nubes esconden el fuego.** El porcentaje de píxeles enmascarados está
   reportado arriba. Todo lo que quedó bajo nube no entra al área quemada, así que
   nuestra cifra es un **piso**, no una estimación insesgada. En la Amazonía en
   octubre, este es el sesgo dominante.
3. **El umbral es una decisión, no un dato.** Con dNBR ≥ 0.10 el área se multiplica;
   con 0.44 se reduce a menos de la mitad. Reportamos 0.27 y mostramos los otros tres
   para que se vea el rango.
4. **WorldCover es de 2021.** Cinco años de frente agrícola en Ucayali desfasan la
   clasificación en una dirección conocida: subestima agricultura y construcción.
5. **Una edificación no es una vivienda.** Open Buildings detecta techos: galpones,
   colegios y corrales cuentan igual que una casa. Y su cobertura cae en bosque denso,
   justo donde el fuego avanza. El número de edificaciones expuestas es, otra vez,
   un piso.

Ninguna invalida el ejercicio: lo delimita. Pasamos de "hubo incendios en Ucayali" a
una cifra de hectáreas con fecha, umbral y nubosidad declaradas, y a un conteo de
construcciones expuestas que ningún reporte oficial publica a esa resolución.
""")

nb = {"cells": C,
      "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python",
                                  "name": "python3"},
                   "language_info": {"name": "python", "version": "3.11"}},
      "nbformat": 4, "nbformat_minor": 5}

out = Path(__file__).parent / "notebooks" / "incendios_manantay.ipynb"
out.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(C)} celdas → {out}")
