"""
Exporta outputs/mapa_nacional.json: focos de todo el Peru y limites
departamentales, proyectados y simplificados, para dibujar el mapa nacional
del tablero sin teselas externas.
"""
import json, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import geopandas as gpd
import numpy as np
import pandas as pd
import datos

SALIDA = RAIZ / "outputs" / "mapa_nacional.json"

focos = datos.focos_7d("viirs-snpp", confianza_minima="n")
dist = datos.distritos()
dep = dist.dissolve(by="departamento").reset_index()[["departamento", "geometry"]]

cruce = gpd.sjoin(focos, dep, how="inner", predicate="within").drop(
    columns="index_right")

# Proyeccion metrica para que el pais no salga deformado
dep_m = dep.to_crs(datos.CRS_METRICO)
focos_m = cruce.to_crs(datos.CRS_METRICO)
t_max = focos["momento"].max()


def anillos(geom, tol=3000):
    g = geom.simplify(tol)
    partes = list(g.geoms) if g.geom_type.startswith("Multi") else [g]
    out = []
    for p in partes:
        if p.is_empty or p.area < 2e7:        # descarta islotes minusculos
            continue
        out.append([[round(x), round(y)] for x, y in p.exterior.coords])
    return out


por_dep = (cruce.groupby("departamento")
                .agg(focos=("frp", "size"), frp=("frp", "sum"))
                .reset_index())

nac = {
    "departamentos": [
        {"nombre": r.departamento.title(),
         "focos": int(por_dep.loc[por_dep.departamento == r.departamento,
                                  "focos"].sum()),
         "anillos": anillos(r.geometry)}
        for _, r in dep_m.iterrows()],
    "focos": [
        {"x": round(float(p.geometry.x)), "y": round(float(p.geometry.y)),
         "f": round(float(p.frp), 1),
         "h": round((t_max - p.momento).total_seconds() / 3600)}
        for _, p in focos_m.iterrows()],
    "limites": [round(v) for v in dep_m.total_bounds],
    "total_focos": int(len(cruce)),
    "ventana": [str(focos.momento.min()), str(focos.momento.max())],
}

SALIDA.write_text(json.dumps(nac, ensure_ascii=False), encoding="utf-8")
print(f"{SALIDA.name}: {len(nac['focos'])} focos, "
      f"{len(nac['departamentos'])} departamentos, "
      f"{SALIDA.stat().st_size/1024:.0f} KB")
