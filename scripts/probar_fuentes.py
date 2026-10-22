"""
Prueba rapida de las seis fuentes que necesitan internet. Corre en ~2 min y
dice exactamente cual falla, en vez de reventar a mitad del notebook.

    python scripts\probar_fuentes.py
"""
import sys, traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import datos

BBOX = (-74.5776, -8.5302, -74.4961, -8.4316)   # AOI de Manantay
ok, fallos = [], []


def probar(nombre, fn):
    print(f"\n--- {nombre} ---")
    try:
        r = fn()
        print(f"OK  {r}")
        ok.append(nombre)
    except Exception as e:
        print(f"FALLA  {type(e).__name__}: {e}")
        traceback.print_exc(limit=2)
        fallos.append(nombre)


def t_firms_7d():
    f = datos.focos_7d("viirs-snpp")
    return f"{len(f):,} focos, {f.momento.min()} -> {f.momento.max()}"


def t_firms_archivo():
    d = datos.focos_ventana("2024-10-12", 10)
    return f"{len(d):,} focos en oct-2024 ({d.procesamiento.iloc[0]})"


def t_stac():
    it = datos.buscar_sentinel2(BBOX, "2026-09-15", "2026-10-21", nubes_max=100)
    return f"{len(it)} escenas Sentinel-2 ({it[0].datetime.date()} .. {it[-1].datetime.date()})"


_ds = {}


def t_leer():
    it = datos.buscar_sentinel2(BBOX, "2026-09-15", "2026-10-21", nubes_max=100)
    _ds["d"] = datos.leer_bandas(it[-1], BBOX, 20)
    d = _ds["d"]
    return (f"{d['B08'].shape} px, {datos.pct_nubes(d):.1f}% invalidos sobre el AOI")


def t_worldcover():
    wc = datos.worldcover(like=_ds["d"])
    return f"{wc.shape} px, misma grilla: {datos.misma_grilla(wc, _ds['d']['B08'])}"


def t_worldpop():
    p = datos.worldpop()
    return f"{p.name}, {p.stat().st_size/1e6:.1f} MB"


def t_openbuildings():
    import geopandas as gpd
    from shapely.geometry import box
    aoi = gpd.GeoDataFrame(geometry=[box(*BBOX)], crs="EPSG:4326")
    e = datos.open_buildings(aoi)
    return f"{len(e):,} edificaciones en el AOI"


for nombre, fn in [("FIRMS 7 dias", t_firms_7d),
                   ("FIRMS archivo (historico)", t_firms_archivo),
                   ("Planetary Computer / STAC", t_stac),
                   ("Leer Sentinel-2 (odc-stac)", t_leer),
                   ("ESA WorldCover (misma grilla)", t_worldcover),
                   ("WorldPop", t_worldpop),
                   ("Google Open Buildings", t_openbuildings)]:
    probar(nombre, fn)

print("\n" + "=" * 60)
print(f"OK:     {len(ok)}  {', '.join(ok)}")
print(f"FALLAN: {len(fallos)}  {', '.join(fallos) if fallos else '-'}")
print("=" * 60)
sys.exit(1 if fallos else 0)
