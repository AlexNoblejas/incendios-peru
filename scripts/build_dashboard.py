"""
Construye outputs/dashboard.html a partir de outputs/hallazgos.json.

Página autocontenida: sin librerías ni llamadas externas salvo la fuente. Las
barras son SVG dibujadas a escala desde los mismos números del JSON, así que
ninguna cifra del tablero está escrita a mano.

    python scripts/build_dashboard.py
"""

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
H = json.loads((RAIZ / "outputs" / "hallazgos.json").read_text(encoding="utf-8"))

nac, his, inc = H["nacional"], H["historico"], H["incendio"]
img, area, exp = H["imagenes"], H["area_quemada"], H["exposicion"]
cob = [c for c in H["que_se_quemo"] if c["hectareas"] > 0][:6]
sev = [s for s in area["por_severidad"] if s["hectareas"] > 0]
lider = his["mayor_anomalia"]
principal = cob[0] if cob else {"clase": "—", "hectareas": 0, "pct": 0}
serie = {int(k): v for k, v in his["serie_anual"].items()}

n = lambda v, d=0: f"{v:,.{d}f}".replace(",", " ")

# Open Buildings puede no haberse podido traer; el tablero lo dice en vez
# de inventar la cifra.
SIN_EDIFICIOS = exp.get("edificaciones_1km_openbuildings") is None


def barras(filas, eti, val, clase, sufijo=" ha", pad=168, ancho=640):
    """Barras horizontales SVG, a escala, con la etiqueta dentro del gráfico."""
    if not filas:
        return "<p class='vacio'>Sin datos.</p>"
    alto_fila = 32
    maximo = max(abs(f[val]) for f in filas) or 1
    alto = alto_fila * len(filas) + 6
    o = [f'<svg viewBox="0 0 {ancho} {alto}" class="barras" role="img">']
    for i, f in enumerate(filas):
        y = i * alto_fila + 3
        w = (abs(f[val]) / maximo) * (ancho - pad - 115)
        o.append(
            f'<text x="{pad - 10}" y="{y + 16}" text-anchor="end" class="b-eti">'
            f'{f[eti]}</text>'
            f'<rect x="{pad}" y="{y + 3}" width="{max(w, 2):.1f}" height="19" '
            f'rx="2" class="{clase}"/>'
            f'<text x="{pad + max(w, 2) + 8:.1f}" y="{y + 17}" class="b-val">'
            f'{n(f[val], 1 if abs(f[val]) < 10 else 0)}{sufijo}</text>')
    o.append("</svg>")
    return "".join(o)


def columnas_serie(serie, destacar, ancho=640, alto=210):
    """Columnas año por año, con la línea del promedio histórico dibujada."""
    anios = sorted(serie)
    if not anios:
        return "<p class='vacio'>Sin serie.</p>"
    maximo = max(serie.values()) or 1
    hist = [serie[a] for a in anios if a != destacar]
    prom = sum(hist) / len(hist) if hist else 0
    izq, abajo, arriba = 46, 28, 10
    w_util = ancho - izq - 8
    h_util = alto - abajo - arriba
    paso = w_util / len(anios)
    bw = min(paso * 0.68, 34)
    o = [f'<svg viewBox="0 0 {ancho} {alto}" class="serie" role="img">']
    # eje y: cero y máximo
    for v in (0, maximo):
        y = arriba + h_util - (v / maximo) * h_util
        o.append(f'<line x1="{izq}" y1="{y:.1f}" x2="{ancho - 8}" y2="{y:.1f}" '
                 f'class="g-eje"/>'
                 f'<text x="{izq - 8}" y="{y + 4:.1f}" text-anchor="end" '
                 f'class="g-num">{n(v)}</text>')
    # promedio histórico
    yp = arriba + h_util - (prom / maximo) * h_util
    o.append(f'<line x1="{izq}" y1="{yp:.1f}" x2="{ancho - 8}" y2="{yp:.1f}" '
             f'class="g-prom"/>'
             f'<text x="{ancho - 10}" y="{yp - 6:.1f}" text-anchor="end" '
             f'class="g-prom-eti">promedio {n(prom)}</text>')
    for i, a in enumerate(anios):
        x = izq + i * paso + (paso - bw) / 2
        h = (serie[a] / maximo) * h_util
        o.append(f'<rect x="{x:.1f}" y="{arriba + h_util - h:.1f}" '
                 f'width="{bw:.1f}" height="{max(h, 1):.1f}" rx="2" '
                 f'class="{"g-foco" if a == destacar else "g-hist"}"/>'
                 f'<text x="{x + bw / 2:.1f}" y="{alto - 9}" '
                 f'text-anchor="middle" class="g-anio'
                 f'{" g-anio-foco" if a == destacar else ""}">'
                 f"'{str(a)[2:]}</text>")
    o.append("</svg>")
    return "".join(o)


# ---------------------------------------------------------------------------
# El mapa: SVG dibujado desde las geometrias reales. Sin teselas externas, asi
# que funciona igual abierto en local o publicado.
# ---------------------------------------------------------------------------
MAPA = RAIZ / "outputs" / "mapa_datos.json"
mapa = json.loads(MAPA.read_text(encoding="utf-8")) if MAPA.exists() else None


def mapa_svg(m, ancho=640, alto=560, margen=14):
    if not m:
        return "<p class='vacio'>Falta outputs/mapa_datos.json.</p>"

    x0, y0, x1, y1 = m["limites"]
    escala = min((ancho - 2 * margen) / (x1 - x0),
                 (alto - 2 * margen) / (y1 - y0))
    dx = margen + ((ancho - 2 * margen) - (x1 - x0) * escala) / 2
    dy = margen + ((alto - 2 * margen) - (y1 - y0) * escala) / 2
    # en pantalla la y crece hacia abajo; en el terreno, hacia arriba
    px = lambda x: dx + (x - x0) * escala
    py = lambda y: dy + (y1 - y) * escala
    camino = lambda anillo: ("M" + "L".join(
        f"{px(x):.1f},{py(y):.1f}" for x, y in anillo) + "Z")

    o = [f'<svg viewBox="0 0 {ancho} {alto}" class="mapa" role="img" '
         f'aria-label="Focos de calor e incendios en Manantay">']
    o.append('<rect width="100%" height="100%" class="m-fondo"/>')

    for anillo in m["distrito"]["anillos"]:
        o.append(f'<path d="{camino(anillo)}" class="m-distrito"/>')

    for inc_ in m["incendios"]:
        clase = "m-huella-pri" if inc_["principal"] else "m-huella"
        titulo = (f'incendio {inc_["id"]} · {inc_["n_focos"]} focos · '
                  f'{inc_["frp"]:,.0f} MW · {inc_["ha"]:,.0f} ha de huella · '
                  f'{inc_["horas"]:.0f} h')
        for anillo in inc_["anillos"]:
            o.append(f'<path d="{camino(anillo)}" class="{clase}">'
                     f'<title>{titulo}</title></path>')

    for anillo in m.get("anillo_1km", []):
        o.append(f'<path d="{camino(anillo)}" class="m-anillo"/>')

    ax0, ay0, ax1, ay1 = m["aoi"]
    o.append(f'<rect x="{px(ax0):.1f}" y="{py(ay1):.1f}" '
             f'width="{(ax1-ax0)*escala:.1f}" height="{(ay1-ay0)*escala:.1f}" '
             f'class="m-aoi"><title>Área analizada con Sentinel-2</title></rect>')

    # el color codifica el dia de deteccion y el radio, la potencia radiativa
    for f in m["focos"]:
        r = 1.8 + min(f["frp"], 40) / 40 * 3.4
        clase = f'm-dia{min(f.get("dia", 0), 2)}'
        o.append(f'<circle cx="{px(f["x"]):.1f}" cy="{py(f["y"]):.1f}" '
                 f'r="{r:.1f}" class="{clase}">'
                 f'<title>{f["cuando"]} UTC · FRP {f["frp"]:,.1f} MW</title>'
                 f'</circle>')

    # escala grafica de 5 km
    km = 5000 * escala
    bx, by = ancho - margen - km, alto - margen - 8
    o.append(f'<line x1="{bx:.1f}" y1="{by:.1f}" x2="{bx+km:.1f}" '
             f'y2="{by:.1f}" class="m-escala"/>'
             f'<text x="{bx+km/2:.1f}" y="{by-6:.1f}" text-anchor="middle" '
             f'class="m-escala-eti">5 km</text>')
    o.append("</svg>")
    return "".join(o)


NAC = RAIZ / "outputs" / "mapa_nacional.json"
nacional = json.loads(NAC.read_text(encoding="utf-8")) if NAC.exists() else None


def mapa_pais(m, ancho=640, alto=720, margen=12):
    """Los focos de toda la semana sobre los limites departamentales."""
    if not m:
        return "<p class='vacio'>Falta outputs/mapa_nacional.json.</p>"
    x0, y0, x1, y1 = m["limites"]
    escala = min((ancho - 2 * margen) / (x1 - x0),
                 (alto - 2 * margen) / (y1 - y0))
    dx = margen + ((ancho - 2 * margen) - (x1 - x0) * escala) / 2
    dy = margen + ((alto - 2 * margen) - (y1 - y0) * escala) / 2
    px = lambda x: dx + (x - x0) * escala
    py = lambda y: dy + (y1 - y) * escala

    o = [f'<svg viewBox="0 0 {ancho} {alto}" class="mapa" role="img" '
         f'aria-label="Focos de calor en el Perú, últimos 7 días">',
         '<rect width="100%" height="100%" class="m-fondo"/>']

    for d in sorted(m["departamentos"], key=lambda d: -d["focos"]):
        clase = "m-dep-alto" if d["focos"] >= 200 else "m-dep"
        for anillo in d["anillos"]:
            camino = "M" + "L".join(f"{px(x):.0f},{py(y):.0f}"
                                    for x, y in anillo) + "Z"
            o.append(f'<path d="{camino}" class="{clase}">'
                     f'<title>{d["nombre"]} · {d["focos"]:,} focos</title></path>')

    # los mas recientes se dibujan al final, para que queden encima
    for f in sorted(m["focos"], key=lambda f: -f["h"]):
        clase = ("m-n24" if f["h"] <= 24 else
                 "m-n72" if f["h"] <= 72 else "m-n7d")
        o.append(f'<circle cx="{px(f["x"]):.0f}" cy="{py(f["y"]):.0f}" '
                 f'r="{1.5 if f["h"] > 24 else 2.1}" class="{clase}"/>')

    km = 200000 * escala
    bx, by = ancho - margen - km - 6, alto - margen - 10
    o.append(f'<line x1="{bx:.0f}" y1="{by:.0f}" x2="{bx+km:.0f}" y2="{by:.0f}" '
             f'class="m-escala"/><text x="{bx+km/2:.0f}" y="{by-6:.0f}" '
             f'text-anchor="middle" class="m-escala-eti">200 km</text>')
    o.append("</svg>")
    return "".join(o)


n24 = sum(1 for f in (nacional or {}).get("focos", []) if f["h"] <= 24)
n72 = sum(1 for f in (nacional or {}).get("focos", []) if 24 < f["h"] <= 72)
n7d = sum(1 for f in (nacional or {}).get("focos", []) if f["h"] > 72)
mapa_pais_html = mapa_pais(nacional)

mapa_html = mapa_svg(mapa)
inc_radio = exp["radio_viviendas_m"]

# un item de leyenda por dia con detecciones; el tamano del punto es el FRP
leyenda_dias = "".join(
    f'<span><i class="l-d{min(i, 2)}"></i>{d}</span>'
    for i, d in enumerate((mapa or {}).get("dias", []))) + \
    '<span class="l-nota">tamaño del punto = potencia radiativa</span>' 

# la figura del área quemada va incrustada: el tablero queda autocontenido
FIG = RAIZ / "figuras" / "05_area_quemada.png"
if FIG.exists():
    import base64
    b64 = base64.b64encode(FIG.read_bytes()).decode()
    figura_quemada = (f'<img src="data:image/png;base64,{b64}" '
                      f'alt="Superficie quemada según dNBR" class="figura">')
else:
    figura_quemada = ""

sev_svg = barras(sev, "clase", "hectareas", "b-sev")
cob_svg = barras(cob, "clase", "hectareas", "b-cob")
serie_svg = columnas_serie(serie, 2026)
anom_svg = barras(
    [{"d": d["departamento"].title(), "v": d["diferencia"]}
     for d in his["por_departamento"][:8]],
    "d", "v", "b-anom", sufijo=" focos", pad=120)

if SIN_EDIFICIOS:
    # La capa no se pudo traer: en su lugar va una cifra que sí tenemos, y el
    # hueco se dice en el texto en vez de rellenarse.
    tarjeta_edificios = f"""<div class="tarjeta">
      <div class="dato">{n(inc["incendios_en_distrito"])}</div>
      <div class="pie">incendios distintos en el distrito</div>
    </div>"""
    parrafo_exposicion = f"""<p>Sobre la exposición: a
  {exp["radio_poblacion_m"] // 1000} km del incendio viven
  <strong>{n(exp["poblacion_5km_worldpop2020"])} personas</strong> (WorldPop 2020,
  celdas de 1 km).</p>
  <p class="aviso">El conteo de edificaciones con Google Open Buildings no se completó
  en esta corrida. Está implementado y el notebook lo intenta; se omite en vez de
  rellenarse.</p>"""
else:
    tarjeta_edificios = f"""<div class="tarjeta">
      <div class="dato">{n(exp["edificaciones_1km_openbuildings"])}</div>
      <div class="pie">edificaciones a menos de {exp["radio_viviendas_m"]} m
      del fuego</div>
    </div>"""
    parrafo_exposicion = f"""<p>Sobre la exposición:
  <strong>{n(exp["edificaciones_1km_openbuildings"])} edificaciones</strong>
  ({n(exp["ha_construidas_1km"], 1)} ha construidas) quedaron a menos de
  {exp["radio_viviendas_m"]} m del fuego, de {n(exp["edificaciones_aoi"])} en el área de
  interés. Esa cifra es el aporte de este trabajo: WorldPop da personas por celda de
  1 km, Google Open Buildings da un polígono por techo.</p>"""

aviso_activo = ""
if img.get("fuego_activo_en_imagen_posterior"):
    aviso_activo = """<p class="aviso"><strong>Fuego activo en la imagen
  posterior.</strong> La toma es del mismo día en que el incendio seguía detectándose,
  así que lo que ardió después no aparece: las hectáreas son un piso adicional por esta
  razón, además de por las nubes. Es la misma salvedad que el ejemplo de clase marcó
  como «fuego activo».</p>"""

sens_filas = "".join(
    f'<tr class="{"destacada" if abs(s["umbral dNBR"] - area["umbral_dnbr"]) < 1e-9 else ""}">'
    f'<td>dNBR ≥ {s["umbral dNBR"]:.2f}</td>'
    f'<td class="num">{n(s["hectáreas"])} ha</td></tr>'
    for s in area["sensibilidad_umbral"])

def pct(v, d=1):
    """Un porcentaje, o una raya si el dato no vino."""
    return "—" if v is None else f"{v:.{d}f} %"


def firmado(v, d=1):
    return "—" if v is None else f"{v:+.{d}f}"


cand_filas = "".join(
    f'<tr><td>{str(c["fecha"])[:10]}</td>'
    f'<td class="num">{pct(c.get("nubes_escena_pct"))}</td>'
    f'<td class="num">{pct(c["invalidos_aoi_pct"])}</td>'
    f'<td class="etq">{etiqueta}</td></tr>'
    for etiqueta, lista in (("antes", img["candidatas_antes"]),
                            ("después", img["candidatas_despues"]))
    for c in lista)

maxdif = max(abs(d["diferencia"]) for d in his["por_departamento"]) or 1


def microbarra(v, maximo, pos="mb-mas", neg="mb-menos"):
    """Una barra dentro de la celda: el signo decide el lado y el color."""
    ancho = min(abs(v) / maximo * 46, 46)
    lado = pos if v >= 0 else neg
    return (f'<span class="mb"><span class="{lado}" '
            f'style="width:{ancho:.0f}%"></span></span>')


dep_filas = "".join(
    f'<tr><td>{d["departamento"].title()}</td>'
    f'<td class="num">{n(d["focos_2026"])}</td>'
    f'<td class="num">{n(d["promedio"], 1)}</td>'
    f'<td class="num">{d["diferencia"]:+,.0f}{microbarra(d["diferencia"], maxdif)}</td>'
    f'<td class="num"><span class="pill {"p-alto" if (d.get("z") or 0) >= 1 else "p-bajo" if (d.get("z") or 0) < 0 else "p-medio"}">{firmado(d.get("z"))}</span></td>'
    f'<td class="num">{d["puesto_en_su_serie"]} / {d["de_n_anios"]}</td></tr>'
    for d in his["por_departamento"][:10])

aviso_anios = ""
if his["anios_faltantes"]:
    aviso_anios = (
        f'<p class="aviso">Años sin cobertura comparable, excluidos y '
        f'<strong>no rellenados</strong>: '
        f'{", ".join(map(str, his["anios_faltantes"]))}.</p>')

HTML = f"""<title>Fuego en Manantay</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Zilla+Slab:wght@500;600;700&family=Public+Sans:wght@400;500;600;700&display=swap">
<style>
/* Tablero oscuro de una columna: cifras arriba, luego temporada, territorio,
   medicion y metodo. Paleta de brasa sobre ceniza oscura; el acento naranja
   marca SIEMPRE 2026 y lo quemado, nunca decora. */
:root {{
  --fondo:#120e0c; --panel:#1b1512; --panel-2:#241c17; --linea:#33281f;
  --tinta:#f4ece5; --tinta-2:#a99687; --tinta-3:#766457;
  --brasa:#ff7a45; --brasa-2:#c1440e; --humo:#8a7565; --frio:#5b9dc9;
  --display:"Zilla Slab",Georgia,serif;
  --texto:"Public Sans",system-ui,-apple-system,sans-serif;
  color-scheme:dark;
}}
body {{ background:var(--fondo); color:var(--tinta); font-family:var(--texto);
       line-height:1.6; }}
.hoja {{ max-width:900px; margin:0 auto;
  padding-left:max(16px,env(safe-area-inset-left,0px));
  padding-right:max(16px,env(safe-area-inset-right,0px));
  padding-block:40px 64px; }}

.eyebrow {{ font-size:.72rem; letter-spacing:.15em; text-transform:uppercase;
  color:var(--brasa); font-weight:700; }}
h1 {{ font-family:var(--display); font-size:clamp(1.9rem,5.5vw,2.9rem);
  line-height:1.1; margin:.3em 0 .2em; text-wrap:balance; font-weight:700; }}
h2 {{ font-family:var(--display); font-size:1.35rem; margin:3rem 0 .2rem;
  text-wrap:balance; font-weight:600; }}
h2 .orden {{ color:var(--tinta-3); font-size:.85em; margin-right:.45em;
  font-variant-numeric:tabular-nums; }}
.lede {{ color:var(--tinta-2); max-width:62ch; margin-top:.2rem; }}
p {{ max-width:64ch; }}
strong {{ color:var(--tinta); }}

.cifras {{ display:grid; gap:10px; margin:1.8rem 0 .4rem;
  grid-template-columns:repeat(auto-fit,minmax(168px,1fr)); }}
.tarjeta {{ border:1px solid var(--linea); border-radius:4px; padding:15px;
  background:var(--panel); min-width:0; }}
.tarjeta .dato {{ font-family:var(--display); font-size:1.95rem; font-weight:700;
  line-height:1.05; font-variant-numeric:tabular-nums; }}
.tarjeta .dato.acento {{ color:var(--brasa); }}
.tarjeta .unidad {{ font-size:.92rem; font-weight:500; color:var(--tinta-2); }}
.tarjeta .pie {{ font-size:.77rem; color:var(--tinta-2); margin-top:.35rem; }}
.corte {{ font-size:.79rem; color:var(--tinta-3); border-top:1px solid var(--linea);
  padding-top:.8rem; margin-top:1.5rem; max-width:70ch; }}

.barras,.serie {{ width:100%; height:auto; margin:.7rem 0 .2rem; }}
.b-eti {{ font:500 12.5px var(--texto); fill:var(--tinta); }}
.b-val {{ font:700 12.5px var(--texto); fill:var(--tinta-2);
  font-variant-numeric:tabular-nums; }}
.b-cob {{ fill:var(--brasa-2); }} .b-sev {{ fill:var(--humo); }}
.b-anom {{ fill:var(--brasa); }}
.g-hist {{ fill:var(--humo); }} .g-foco {{ fill:var(--brasa); }}
.g-eje {{ stroke:var(--linea); stroke-width:1; }}
.g-prom {{ stroke:var(--frio); stroke-width:1.2; stroke-dasharray:5 4; }}
.g-prom-eti {{ font:600 11px var(--texto); fill:var(--frio); }}
.g-num {{ font:500 11px var(--texto); fill:var(--tinta-3);
  font-variant-numeric:tabular-nums; }}
.g-anio {{ font:500 10.5px var(--texto); fill:var(--tinta-3); }}
.g-anio-foco {{ fill:var(--brasa); font-weight:700; }}

.barra {{ position:sticky; top:env(safe-area-inset-top,0px); z-index:20;
  display:flex; flex-wrap:wrap; align-items:center; gap:.1rem .9rem;
  background:rgba(18,14,12,.94); border-bottom:1px solid var(--linea);
  padding:.6rem max(16px,env(safe-area-inset-left,0px));
  font-size:.82rem; backdrop-filter:blur(8px); }}
.barra .marca {{ font-weight:700; color:var(--tinta); margin-right:.5rem;
  display:flex; align-items:center; gap:.45rem; }}
.barra .punto {{ width:9px; height:9px; border-radius:50%;
  background:var(--brasa); flex:none; }}
.barra a {{ color:var(--tinta-2); text-decoration:none; padding:.2rem 0;
  border-bottom:1.5px solid transparent; }}
.barra a:hover {{ color:var(--brasa); border-bottom-color:var(--brasa); }}
body::before {{ content:""; position:fixed; inset:0 0 auto;
  height:env(safe-area-inset-top,0px); z-index:21; background:var(--fondo); }}

.m-dep {{ fill:var(--panel-2); stroke:var(--linea); stroke-width:.7; }}
.m-dep-alto {{ fill:#2b211a; stroke:var(--tinta-3); stroke-width:.8; }}
.m-n24 {{ fill:#ff2d00; }}
.m-n72 {{ fill:#ff9d4d; fill-opacity:.9; }}
.m-n7d {{ fill:#ffd9a0; fill-opacity:.65; }}
.l-n24 {{ background:#ff2d00; }}
.l-n72 {{ background:#ff9d4d; }}
.l-n7d {{ background:#ffd9a0; }}

.mb {{ display:block; height:3px; margin-top:3px; background:var(--linea);
  border-radius:2px; overflow:hidden; }}
.mb span {{ display:block; height:100%; border-radius:2px; }}
.mb-mas {{ background:var(--brasa); }}
.mb-menos {{ background:var(--frio); }}
.pill {{ display:inline-block; padding:.05rem .4rem; border-radius:3px;
  font-size:.82rem; font-weight:700; }}
.p-alto {{ background:rgba(255,122,69,.18); color:var(--brasa); }}
.p-medio {{ color:var(--tinta-2); }}
.p-bajo {{ background:rgba(91,157,201,.16); color:var(--frio); }}

.mapa {{ width:100%; height:auto; margin:.9rem 0 .4rem;
  border:1px solid var(--linea); border-radius:4px; }}
.m-fondo {{ fill:var(--panel); }}
.m-distrito {{ fill:var(--panel-2); stroke:var(--tinta-3); stroke-width:1.1; }}
.m-huella {{ fill:var(--brasa-2); fill-opacity:.30; stroke:var(--brasa-2);
  stroke-width:.7; }}
.m-huella-pri {{ fill:var(--brasa); fill-opacity:.42; stroke:var(--brasa);
  stroke-width:1.1; }}
.m-anillo {{ fill:none; stroke:var(--brasa); stroke-width:1.1;
  stroke-dasharray:5 4; }}
.m-aoi {{ fill:none; stroke:var(--frio); stroke-width:1.1;
  stroke-dasharray:3 3; }}
.m-dia0 {{ fill:#ffd9a0; fill-opacity:.9; }}
.m-dia1 {{ fill:#ff9d4d; fill-opacity:.9; }}
.m-dia2 {{ fill:#e02200; fill-opacity:.95; }}
.m-escala {{ stroke:var(--tinta-2); stroke-width:1.6; }}
.m-escala-eti {{ font:600 10.5px var(--texto); fill:var(--tinta-2); }}
.mapa path, .mapa circle, .mapa rect {{ transition:none; }}
.mapa circle:hover {{ stroke:var(--tinta); stroke-width:1; }}

.leyenda {{ display:flex; flex-wrap:wrap; gap:.5rem 1.1rem; font-size:.78rem;
  color:var(--tinta-2); margin:.1rem 0 .7rem; }}
.leyenda span {{ display:flex; align-items:center; gap:.4rem; }}
.leyenda i {{ width:12px; height:12px; border-radius:50%; flex:none; }}
.leyenda .l-nota {{ color:var(--tinta-3); font-style:italic; }}
.l-d0 {{ background:#ffd9a0; }}
.l-d1 {{ background:#ff9d4d; }}
.l-d2 {{ background:#e02200; }}
.l-pri {{ background:var(--brasa); opacity:.55; border-radius:2px !important; }}
.l-hue {{ background:var(--brasa-2); opacity:.4; border-radius:2px !important; }}
.l-anillo {{ border:1.5px dashed var(--brasa); border-radius:2px !important; }}
.l-aoi {{ border:1.5px dashed var(--frio); border-radius:2px !important; }}

.figura {{ width:100%; height:auto; border:1px solid var(--linea);
  border-radius:4px; margin:.7rem 0 .3rem; background:var(--panel); }}
h3.sub-h {{ font-family:var(--display); font-size:1.05rem; font-weight:600;
  color:var(--tinta); text-transform:none; letter-spacing:0;
  margin:1.9rem 0 .2rem; }}
.scroll {{ overflow-x:auto; margin:.8rem 0; }}
table {{ border-collapse:collapse; width:100%; font-size:.9rem; }}
th,td {{ text-align:left; padding:.45rem .7rem; border-bottom:1px solid var(--linea);
  white-space:nowrap; }}
th {{ font-size:.72rem; letter-spacing:.07em; text-transform:uppercase;
  color:var(--tinta-3); font-weight:700; }}
td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
td.etq {{ color:var(--tinta-3); font-size:.82rem; }}
tr.destacada td {{ background:var(--panel-2); color:var(--brasa); font-weight:700; }}

.cadena {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.8rem;
  background:var(--panel); border:1px solid var(--linea);
  border-left:3px solid var(--brasa); border-radius:3px; padding:14px 16px;
  white-space:pre; overflow-x:auto; line-height:1.55; color:var(--tinta-2); }}
.aviso {{ font-size:.86rem; color:var(--tinta); background:var(--panel-2);
  border-left:3px solid var(--frio); border-radius:3px; padding:11px 14px;
  max-width:66ch; }}
.nota {{ font-size:.84rem; color:var(--tinta-2); max-width:64ch; }}
ol.limites {{ padding-left:1.15rem; max-width:64ch; color:var(--tinta-2); }}
ol.limites li {{ margin-bottom:.65rem; }}
.vacio {{ color:var(--tinta-3); font-style:italic; }}
.glosario {{ display:grid; gap:10px; margin:1rem 0;
  grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); }}
.glosario div {{ border:1px solid var(--linea); border-radius:4px; padding:12px 14px;
  background:var(--panel); min-width:0; }}
.glosario dt {{ font-weight:700; font-size:.82rem; color:var(--brasa);
  margin-bottom:.2rem; }}
.glosario dd {{ margin:0; font-size:.84rem; color:var(--tinta-2); }}
.pie-pagina {{ margin-top:3rem; padding-top:1rem; border-top:1px solid var(--linea);
  font-size:.79rem; color:var(--tinta-3); max-width:70ch; }}
</style>

<nav class="barra">
  <span class="marca"><i class="punto"></i>Fuego en Manantay</span>
  <a href="#resumen">Resumen</a>
  <a href="#temporada">Temporada</a>
  <a href="#departamentos">Departamentos</a>
  <a href="#mapa">Mapa</a>
  <a href="#incendio">El incendio</a>
  <a href="#metodo">Fuentes y método</a>
</nav>

<div class="hoja">
  <p class="eyebrow">{H['departamento'].title()} · {H['provincia'].title()} · UBIGEO {H['ubigeo']}</p>
  <h1>Fuego en Manantay</h1>
  <p class="lede">Cuánto se quemó, qué se quemó, a cuántas construcciones llegó — y si
  esta semana de octubre es excepcional frente a catorce años de la misma ventana.</p>

  <h2 id="resumen"><span class="orden">01</span>Resumen</h2>
  <div class="cifras">
    <div class="tarjeta">
      <div class="dato acento">{n(area['hectareas'])}<span class="unidad"> ha</span></div>
      <div class="pie">quemadas · dNBR ≥ {area['umbral_dnbr']}</div>
    </div>
    <div class="tarjeta">
      <div class="dato acento">{his['variacion_pct']:+.0f}<span class="unidad"> %</span></div>
      <div class="pie">focos de 2026 vs. promedio 2012–2025, misma ventana</div>
    </div>
    {tarjeta_edificios}
    <div class="tarjeta">
      <div class="dato">{n(exp['poblacion_5km_worldpop2020'])}</div>
      <div class="pie">personas a {exp['radio_poblacion_m'] // 1000} km · WorldPop 2020</div>
    </div>
    <div class="tarjeta">
      <div class="dato">{his['departamentos_sobre_su_promedio']}<span class="unidad"> / {his['de_n_departamentos']}</span></div>
      <div class="pie">departamentos sobre su propio promedio</div>
    </div>
    <div class="tarjeta">
      <div class="dato">{img['pixeles_utilizables_pct']}<span class="unidad"> %</span></div>
      <div class="pie">del área de interés sin nube en ambas fechas</div>
    </div>
  </div>

  <p class="corte">Corte: {H['corte']}. Imágenes Sentinel-2 L2A del
  {img['antes']['fecha']} y del {img['despues']['fecha']},
  separadas por {img['dias_entre']} días, a {img['resolucion_m']} m.
  Trabajo académico; no reemplaza los reportes del COEN, INDECI, SERFOR ni SERNANP.</p>

  <h2 id="temporada"><span class="orden">02</span>Temporada · ¿es 2026 excepcional?</h2>
  <p>La misma ventana calendario ({his['ventana_calendario']}) en cada año, para que la
  comparación valga: <strong>{n(his['focos_2026'])} focos en 2026</strong> frente a un
  promedio de {n(his['promedio_2012_2025'])}. Es el puesto
  <strong>{his['puesto_2026']} de {his['de_n_anios']}</strong> años de la serie.</p>
  {serie_svg}
  {aviso_anios}
  <p class="aviso"><strong>Comparabilidad.</strong> {his['aviso_sensores']}
  El NRT no está revalidado, así que parte de la diferencia puede venir del
  procesamiento y no del fuego.</p>

  <h2 id="departamentos"><span class="orden">03</span>Departamentos · quién explica la diferencia</h2>
  <p>La mayor anomalía absoluta es <strong>{lider['departamento'].title()}</strong>:
  {n(lider['focos_2026'])} focos contra un promedio de {n(lider['promedio'])}
  ({lider['diferencia']:+,.0f}{"" if lider.get("z") is None else f", z = {lider['z']:+.1f}"}).</p>
  {anom_svg}
  <div class="scroll">
    <table>
      <thead><tr><th>Departamento</th><th class="num">2026</th>
      <th class="num">Prom. 12–25</th><th class="num">Dif.</th>
      <th class="num">z</th><th class="num">Puesto en su serie</th></tr></thead>
      <tbody>{dep_filas}</tbody>
    </table>
  </div>

  <h2 id="mapa"><span class="orden">04</span>El mapa</h2>
  <h3 class="sub-h">Dónde arde el país</h3>
  <p>Los {n(nacional["total_focos"]) if nacional else "—"} focos de calor de los últimos
  siete días, sobre los límites departamentales. Los departamentos con 200 focos o más
  van resaltados; pasa el cursor para ver el conteo de cada uno.</p>
  {mapa_pais_html}
  <div class="leyenda">
    <span><i class="l-n24"></i>últimas 24 h ({n(n24)})</span>
    <span><i class="l-n72"></i>1 a 3 días ({n(n72)})</span>
    <span><i class="l-n7d"></i>3 a 7 días ({n(n7d)})</span>
    <span class="l-nota">proyección UTM 18S</span>
  </div>

  <h3 class="sub-h">El zoom: Manantay</h3>
  <p>Los {n(inc['focos_en_distrito'])} focos de la semana dentro de Manantay, agrupados
  en {inc['incendios_en_distrito']} incendios. El tamaño de cada punto es su potencia
  radiativa; pasa el cursor para ver la hora y los megavatios.</p>
  {mapa_html}
  <div class="leyenda">
    {leyenda_dias}
    <span><i class="l-pri"></i>huella del incendio principal</span>
    <span><i class="l-hue"></i>otras huellas VIIRS</span>
    <span><i class="l-anillo"></i>anillo de {inc_radio} m</span>
    <span><i class="l-aoi"></i>área analizada con Sentinel-2</span>
  </div>
  <p class="nota">Dibujado desde las geometrías reales en UTM 18S, sin mapa base: el
  tablero no depende de ningún servidor de teselas. El mapa navegable, con fondo
  satelital, está en <code>outputs/mapa_manantay.html</code>.</p>

  <h3 class="sub-h">Lo que midió Sentinel-2</h3>
  {figura_quemada}
  <p class="nota">En amarillo, los píxeles con dNBR ≥ {area['umbral_dnbr']}. En blanco,
  lo que quedó bajo nube en alguna de las dos fechas y por tanto no entra al cálculo.</p>

  <h2 id="incendio"><span class="orden">05</span>Atención prioritaria · el incendio medido</h2>
  <p>En Manantay, {inc['focos_en_distrito']} focos se agruparon en
  <strong>{inc['incendios_en_distrito']} incendios</strong> con la regla de ≤ 1 km y
  ≤ 48 h. El de mayor energía concentró {inc['n_focos']} focos y
  {n(inc['frp_total_mw'])} MW durante {inc['horas_activo']:.0f} horas.</p>
  <div class="cifras">
    <div class="tarjeta">
      <div class="dato">{n(inc['huella_viirs_ha'])}<span class="unidad"> ha</span></div>
      <div class="pie">huella VIIRS · <strong>proxy, no área quemada</strong></div>
    </div>
    <div class="tarjeta">
      <div class="dato acento">{n(area['hectareas'])}<span class="unidad"> ha</span></div>
      <div class="pie">área quemada medida con dNBR</div>
    </div>
    <div class="tarjeta">
      <div class="dato">{n(inc['frp_max_mw'], 1)}<span class="unidad"> MW</span></div>
      <div class="pie">el foco más intenso</div>
    </div>
  </div>
  {sev_svg}
  <p class="nota">Hectáreas por clase de severidad, umbrales de Key &amp; Benson (USGS).
  <strong>No son universales</strong>: dependen del ecosistema, del sensor, de las fechas
  y de una validación de campo que acá no existe.</p>

  <h2><span class="orden">06</span>El número depende del umbral</h2>
  <p>La misma imagen, cuatro fronteras entre «quemado» y «no quemado». Reportamos
  {area['umbral_dnbr']}; las otras tres son el intervalo de lo defendible.</p>
  <div class="scroll">
    <table>
      <thead><tr><th>Umbral</th><th class="num">Superficie</th></tr></thead>
      <tbody>{sens_filas}</tbody>
    </table>
  </div>
  <p class="nota">Y estas son las imágenes candidatas. Las dos columnas de nube son
  distintas y por eso se reportan las dos: la de la escena cubre 110 × 110 km, la del
  área de interés es la que de verdad afecta al incendio. <strong>La elección se hizo
  por la segunda</strong>, no por la primera.</p>
  {aviso_activo}
  <div class="scroll">
    <table>
      <thead><tr><th>Fecha</th><th class="num">Nube de la escena</th>
      <th class="num">Inválidos sobre el AOI</th><th></th></tr></thead>
      <tbody>{cand_filas}</tbody>
    </table>
  </div>

  <h2><span class="orden">07</span>Qué se quemó, y a quién llegó</h2>
  <p>El fuego no cayó sobre territorio vacío: la clase dominante fue
  <strong>{principal['clase'].lower()}</strong>, con {n(principal['hectareas'])} ha
  ({principal['pct']:.0f} % de lo quemado).</p>
  {cob_svg}
  <p class="nota">ESA WorldCover 2021 cargado sobre la misma grilla que el dNBR, con
  remuestreo nearest-neighbor por ser categórico. Es de 2021 y el fuego de 2026: cinco
  años de frente agrícola en Ucayali desfasan la clasificación, subestimando agricultura
  y construcción.</p>
  {parrafo_exposicion}

  <h2 id="metodo"><span class="orden">08</span>Fuentes y método</h2>
  <div class="cadena">focos VIIRS S-NPP, 7 dias (NASA FIRMS)
  |- confianza >= nominal            descarta reflejos y fuentes fijas
  |- sjoin con distritos INEI         {n(nac['focos_7d'])} focos, {n(nac['distritos_con_fuego'])} distritos con fuego
  |- DBSCAN <= 1 km y <= 48 h         {inc['focos_en_distrito']} focos -> {inc['incendios_en_distrito']} incendios en Manantay
       |- prioridad = log(1+FRP) x log(1+huella) x (1 + focos 24 h)

serie historica, MISMA ventana calendario cada anio
  |- 2012-2025 archivo SP · 2026 NRT  marcado foco por foco
  |- anios sin cobertura: se excluyen y se avisa, NO se rellenan
  |- por departamento: promedio, mediana, maximo, sigma, z, puesto

Sentinel-2 L2A, grilla comun UTM 18S a {img['resolucion_m']} m
  |- candidatas con fecha, nube de escena y % invalido sobre el AOI
  |- se elige por el % sobre el AOI (SCL), NO por eo:cloud_cover
  |- inspeccion previa: CRS, tamano, bandas, nodata, dtype, validos
  |- assert misma_grilla() antes de restar
  |- NBR = (B08 - B12)/(B08 + B12);  dNBR = NBR_antes - NBR_despues
       |- umbral {area['umbral_dnbr']}                   {n(area['hectareas'])} ha

cruces sobre la misma mascara de quemado
  |- ESA WorldCover con like= la escena, nearest-neighbor
  |- WorldPop 1 km, anillo {exp['radio_poblacion_m'] // 1000} km            {n(exp['poblacion_5km_worldpop2020'])} personas
  |- Open Buildings, anillo {exp['radio_viviendas_m']} m      {"no disponible en esta corrida" if SIN_EDIFICIOS else f"{n(exp['edificaciones_1km_openbuildings'])} edificaciones"}</div>

  <p class="nota">Todas las fuentes son públicas. La única que pide clave es FIRMS, y se
  lee de <code>.env</code>, nunca del código. Todo corre en CPU.</p>

  <h2>Cuatro cosas que no son lo mismo</h2>
  <div class="glosario">
    <div><dt>Foco de calor</dt><dd>Un píxel donde el satélite midió una anomalía
    térmica. Puede ser un fuego forestal, una quema agrícola o un horno.</dd></div>
    <div><dt>Incendio</dt><dd>Un grupo de focos a ≤ 1 km y ≤ 48 h. Es una regla nuestra,
    no una categoría del dato.</dd></div>
    <div><dt>Huella VIIRS</dt><dd>El buffer de 375 m alrededor de los focos. Proxy
    operativo: sobreestima los fuegos puntuales y subestima los grandes.</dd></div>
    <div><dt>Área quemada</dt><dd>Lo medido con dNBR sobre Sentinel-2. Es la única de las
    cuatro que se mide en hectáreas de suelo afectado.</dd></div>
  </div>

  <h2>Lo que estos números no dicen</h2>
  <ol class="limites">
    <li><strong>Un foco de calor no es un incendio.</strong> Quemas agrícolas
    controladas, hornos ladrilleros y fuegos forestales entran al mismo conteo.</li>
    <li><strong>La huella VIIRS no es área quemada.</strong> Por eso se reportan
    separadas: {n(inc['huella_viirs_ha'])} ha de huella frente a
    {n(area['hectareas'])} ha medidas con dNBR.</li>
    <li><strong>Las nubes esconden el fuego.</strong> Quedó utilizable el
    {img['pixeles_utilizables_pct']} % del área de interés; lo tapado no entra. Las
    {n(area['hectareas'])} ha son un <strong>piso</strong>, no una estimación
    insesgada. En la Amazonía en octubre, este es el sesgo dominante.</li>
    <li><strong>El umbral es una decisión, no un dato.</strong> Ver la sección 06.</li>
    <li><strong>La serie histórica mezcla procesamientos</strong> (SP y NRT). Mismo
    satélite, distinta validación.</li>
    <li><strong>Una edificación no es una vivienda.</strong> Open Buildings detecta
    techos, y su cobertura cae en bosque denso. El conteo de expuestas es, otra vez,
    un piso.</li>
  </ol>

  <p class="pie-pagina">Alexander Noblejas · Ciencia de Datos con Python, Diplomatura
  QLAB · 21 de octubre de 2026.<br>
  Datos: NASA FIRMS (VIIRS S-NPP) · Sentinel-2 L2A y ESA WorldCover vía Microsoft
  Planetary Computer · WorldPop 2020 · Google Open Buildings v3 · límites INEI (UBIGEO).
  </p>
</div>
"""

destino = RAIZ / "outputs" / "dashboard.html"
destino.write_text(HTML, encoding="utf-8")
print(f"dashboard.html escrito · {len(HTML):,} bytes")
