"""
Exporta outputs/mapa_datos.json: las geometrias del mapa, ya proyectadas y
simplificadas, para que el tablero las dibuje como SVG sin depender de
servidores de teselas.

    python scripts/exportar_mapa.py
"""
import json, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import geopandas as gpd
import numpy as np
import pandas as pd
import datos

SALIDA = RAIZ / "outputs" / "mapa_datos.json"


def anillos(geom, tol):
    """Poligono (o multi) -> lista de anillos exteriores simplificados."""
    g = geom.simplify(tol)
    partes = list(g.geoms) if g.geom_type.startswith("Multi") else [g]
    return [[[round(x, 1), round(y, 1)] for x, y in p.exterior.coords]
            for p in partes if not p.is_empty]


focos = datos.focos_7d("viirs-snpp", confianza_minima="n")
zona = datos.distrito("MANANTAY", "UCAYALI")
fz = gpd.sjoin(focos, zona[["geometry"]], predicate="within").drop(
    columns="index_right")
agr = datos.agrupar_incendios(fz, radio_km=1.0, horas=48.0)
inc = datos.resumen_incendios(agr, buffer_m=375)

EVENTO = inc.sort_values("frp_total", ascending=False).iloc[0]
zona_m = datos.a_metros(zona)
focos_m = datos.a_metros(agr)

# el reloj se ancla al ultimo foco del PAIS, no al del distrito: si no, todo
# lo del distrito parece "de las ultimas 24 h"
t_max = focos["momento"].max()
dias = sorted(agr["momento"].dt.strftime("%Y-%m-%d").unique())

mapa = {
    "distrito": {"nombre": "Manantay",
                 "anillos": anillos(zona_m.geometry.iloc[0], 60)},
    "aoi": list(np.round(
        gpd.GeoSeries([EVENTO.geometry.buffer(2000)],
                      crs=datos.CRS_METRICO).total_bounds, 1)),
    "anillo_1km": anillos(EVENTO.geometry.buffer(1000), 40),
    "incendios": [
        {"id": int(r.incendio_id), "n_focos": int(r.n_focos),
         "frp": round(float(r.frp_total), 1),
         "ha": round(float(r.huella_ha), 1),
         "horas": round(float(r.horas), 1),
         "principal": bool(r.incendio_id == EVENTO.incendio_id),
         "anillos": anillos(r.geometry, 40)}
        for _, r in inc.iterrows()],
    "focos": [
        {"x": round(float(p.geometry.x), 1), "y": round(float(p.geometry.y), 1),
         "frp": round(float(p.frp), 1),
         "h": round((t_max - p.momento).total_seconds() / 3600, 1),
         "dia": dias.index(p.momento.strftime("%Y-%m-%d")),
         "cuando": p.momento.strftime("%d-%b %H:%M")}
        for _, p in focos_m.iterrows()],
    "dias": [pd.Timestamp(d).strftime("%d-%b") for d in dias],
    "limites": list(np.round(zona_m.total_bounds, 1)),
}

SALIDA.write_text(json.dumps(mapa, ensure_ascii=False), encoding="utf-8")
print(f"{SALIDA.name}: {len(mapa['focos'])} focos, "
      f"{len(mapa['incendios'])} incendios, "
      f"{SALIDA.stat().st_size/1024:.0f} KB")
