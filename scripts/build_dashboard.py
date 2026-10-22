"""
Construye outputs/dashboard.html a partir de outputs/hallazgos.json.

Página autocontenida: sin librerías, sin llamadas externas salvo la fuente.
Las barras son SVG dibujadas a escala desde los mismos números del JSON.

    python scripts/build_dashboard.py
"""

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
H = json.loads((RAIZ / "outputs" / "hallazgos.json").read_text(encoding="utf-8"))

inc, img, area, exp, foc = (H["incendio"], H["imagenes"], H["area_quemada"],
                            H["exposicion"], H["focos"])
cob = [c for c in H["que_se_quemo"] if c["hectareas"] > 0][:6]
sev = [s for s in area["por_severidad"]
       if s["hectareas"] > 0 and "Severidad" in s["clase"]]
sens = area["sensibilidad_umbral"]

n = lambda v, d=0: f"{v:,.{d}f}".replace(",", " ")


def barras(filas, etiqueta_clave, valor_clave, clase, sufijo=" ha"):
    """Barras horizontales en SVG, a escala, con la etiqueta dentro del gráfico."""
    if not filas:
        return "<p class='vacio'>Sin datos en esta categoría.</p>"
    alto_fila, pad_izq, ancho = 34, 150, 560
    maximo = max(f[valor_clave] for f in filas) or 1
    alto = alto_fila * len(filas) + 8
    out = [f'<svg viewBox="0 0 {ancho} {alto}" role="img" class="barras">']
    for i, f in enumerate(filas):
        y = i * alto_fila + 4
        w = (f[valor_clave] / maximo) * (ancho - pad_izq - 110)
        out.append(
            f'<text x="{pad_izq - 10}" y="{y + 17}" text-anchor="end" '
            f'class="b-eti">{f[etiqueta_clave]}</text>'
            f'<rect x="{pad_izq}" y="{y + 4}" width="{max(w, 2):.1f}" height="20" '
            f'rx="3" class="{clase}"/>'
            f'<text x="{pad_izq + max(w, 2) + 8:.1f}" y="{y + 18}" class="b-val">'
            f'{n(f[valor_clave])}{sufijo}</text>')
    out.append("</svg>")
    return "".join(out)


cob_svg = barras(cob, "clase", "hectareas", "b-cob")
sev_svg = barras(sev, "clase", "hectareas", "b-sev")

sens_filas = "".join(
    f'<tr class="{"destacada" if abs(s["umbral dNBR"] - area["umbral_dnbr"]) < 1e-9 else ""}">'
    f'<td>dNBR ≥ {s["umbral dNBR"]:.2f}</td>'
    f'<td class="num">{n(s["hectáreas"])} ha</td></tr>' for s in sens)

cob_principal = cob[0] if cob else {"clase": "—", "pct": 0, "hectareas": 0}

HTML = f"""<title>Fuego en Manantay</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Zilla+Slab:wght@400;600;700&family=Public+Sans:wght@400;500;700&display=swap">
<style>
/* Una columna de lectura; las cifras viven en tarjetas de borde fino, sin sombras.
   Paleta de brasa y ceniza: neutros con sesgo cálido, acento naranja quemado. */
:root {{
  --ceniza-0:#faf7f4; --ceniza-1:#f1ebe5; --ceniza-2:#ddd3ca;
  --tinta:#241c17; --tinta-suave:#6b5d53;
  --brasa:#c1440e; --humo-barra:#7d6a5c; --linea:#e0d7ce;
  --display:"Zilla Slab",Georgia,serif;
  --texto:"Public Sans",system-ui,-apple-system,sans-serif;
  color-scheme:light;
}}
@media (prefers-color-scheme:dark) {{
  :root:not([data-theme="light"]) {{
    --ceniza-0:#17120f; --ceniza-1:#211a16; --ceniza-2:#352b24;
    --tinta:#f3ece6; --tinta-suave:#b3a296;
    --brasa:#ff7a45; --humo-barra:#9b8574; --linea:#352b24;
    color-scheme:dark;
  }}
}}
:root[data-theme="dark"] {{
  --ceniza-0:#17120f; --ceniza-1:#211a16; --ceniza-2:#352b24;
  --tinta:#f3ece6; --tinta-suave:#b3a296;
  --brasa:#ff7a45; --humo-barra:#9b8574; --linea:#352b24;
  color-scheme:dark;
}}
body {{ background:var(--ceniza-0); color:var(--tinta); font-family:var(--texto);
       line-height:1.6; }}
.hoja {{ max-width:860px; margin:0 auto;
  padding-left:max(16px,env(safe-area-inset-left,0px));
  padding-right:max(16px,env(safe-area-inset-right,0px));
  padding-block:40px 64px; }}
.eyebrow {{ font-size:.72rem; letter-spacing:.14em; text-transform:uppercase;
  color:var(--brasa); font-weight:700; }}
h1 {{ font-family:var(--display); font-size:clamp(2rem,6vw,3.1rem); line-height:1.08;
  margin:.3em 0 .15em; text-wrap:balance; font-weight:700; }}
h2 {{ font-family:var(--display); font-size:1.42rem; margin:2.6rem 0 .6rem;
  text-wrap:balance; }}
h3 {{ font-size:.86rem; letter-spacing:.08em; text-transform:uppercase;
  color:var(--tinta-suave); margin:1.8rem 0 .5rem; font-weight:700; }}
p {{ max-width:64ch; }}
.sub {{ color:var(--tinta-suave); max-width:60ch; }}
.corte {{ font-size:.8rem; color:var(--tinta-suave);
  border-top:1px solid var(--linea); padding-top:.8rem; margin-top:1.6rem; }}

.cifras {{ display:grid; gap:12px; margin:1.8rem 0 .5rem;
  grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); }}
.tarjeta {{ border:1px solid var(--linea); border-radius:4px; padding:16px 16px 14px;
  background:var(--ceniza-1); min-width:0; }}
.tarjeta .dato {{ font-family:var(--display); font-size:2.05rem; font-weight:700;
  line-height:1.05; font-variant-numeric:tabular-nums; }}
.tarjeta .dato.acento {{ color:var(--brasa); }}
.tarjeta .pie {{ font-size:.78rem; color:var(--tinta-suave); margin-top:.3rem; }}
.tarjeta .unidad {{ font-size:.95rem; font-weight:500; }}

.barras {{ width:100%; height:auto; margin:.6rem 0 .2rem; }}
.b-cob {{ fill:var(--brasa); }}
.b-sev {{ fill:var(--humo-barra); }}
.b-eti {{ font:500 12.5px var(--texto); fill:var(--tinta); }}
.b-val {{ font:700 12.5px var(--texto); fill:var(--tinta-suave);
  font-variant-numeric:tabular-nums; }}

.scroll {{ overflow-x:auto; }}
table {{ border-collapse:collapse; width:100%; font-size:.92rem; }}
th,td {{ text-align:left; padding:.5rem .7rem; border-bottom:1px solid var(--linea); }}
th {{ font-size:.74rem; letter-spacing:.07em; text-transform:uppercase;
  color:var(--tinta-suave); }}
td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
tr.destacada td {{ background:var(--ceniza-2); font-weight:700; color:var(--tinta); }}

.cadena {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.82rem;
  background:var(--ceniza-1); border:1px solid var(--linea); border-left:3px solid var(--brasa);
  border-radius:3px; padding:14px 16px; white-space:pre; overflow-x:auto;
  line-height:1.5; }}
ol.limites {{ padding-left:1.1rem; max-width:64ch; }}
ol.limites li {{ margin-bottom:.7rem; }}
.vacio {{ color:var(--tinta-suave); font-style:italic; }}
.nota {{ font-size:.85rem; color:var(--tinta-suave); max-width:62ch; }}
.pie-pagina {{ margin-top:3rem; padding-top:1rem; border-top:1px solid var(--linea);
  font-size:.8rem; color:var(--tinta-suave); }}
</style>

<div class="hoja">
  <p class="eyebrow">Ucayali · Coronel Portillo · UBIGEO {H['ubigeo']}</p>
  <h1>¿Cuánto se quemó en Manantay, y a quién llegó?</h1>
  <p class="sub">Un incendio de octubre de 2026 medido con imágenes satelitales:
  cuántas hectáreas, qué cubría el suelo que ardió, y cuántas construcciones
  quedaron al borde del fuego.</p>

  <div class="cifras">
    <div class="tarjeta">
      <div class="dato acento">{n(area['hectareas'])}<span class="unidad"> ha</span></div>
      <div class="pie">quemadas · dNBR ≥ {area['umbral_dnbr']}</div>
    </div>
    <div class="tarjeta">
      <div class="dato">{n(exp['edificaciones_1km_openbuildings'])}</div>
      <div class="pie">edificaciones a menos de 1 km</div>
    </div>
    <div class="tarjeta">
      <div class="dato">{n(exp['poblacion_5km_worldpop2020'])}</div>
      <div class="pie">personas a 5 km · WorldPop 2020</div>
    </div>
    <div class="tarjeta">
      <div class="dato">{img['pixeles_utilizables_pct']}<span class="unidad"> %</span></div>
      <div class="pie">del recorte sin nube en ambas fechas</div>
    </div>
  </div>

  <p class="corte">Corte: {H['corte']} · Imágenes Sentinel-2 L2A del
  {img['antes']['fecha']} ({img['antes']['nubes_recorte_pct']} % de nube sobre el
  recorte) y del {img['despues']['fecha']}
  ({img['despues']['nubes_recorte_pct']} %), separadas por {img['dias_entre']} días.
  Trabajo académico; no reemplaza los reportes del COEN, INDECI, SERFOR ni SERNANP.</p>

  <h2>Qué se quemó</h2>
  <p>El fuego no cayó sobre territorio vacío: la clase dominante fue
  <strong>{cob_principal['clase'].lower()}</strong>, con {n(cob_principal['hectareas'])} ha
  ({cob_principal['pct']:.0f} % de la superficie quemada).</p>
  {cob_svg}
  <p class="nota">Hectáreas quemadas por clase de ESA WorldCover 2021, contadas sobre
  la misma máscara de dNBR. La cobertura es de 2021 y el fuego de 2026: cinco años de
  frente agrícola en Ucayali desfasan la clasificación.</p>

  <h2>Con qué severidad</h2>
  {sev_svg}
  <p class="nota">Umbrales de Key &amp; Benson (USGS).</p>

  <h2>El número depende del umbral</h2>
  <p>La misma imagen, cuatro fronteras entre «quemado» y «no quemado». Reportamos
  {area['umbral_dnbr']}; las otras tres son el intervalo de lo defendible.</p>
  <div class="scroll">
    <table>
      <thead><tr><th>Umbral</th><th class="num">Superficie</th></tr></thead>
      <tbody>{sens_filas}</tbody>
    </table>
  </div>

  <h2>Cómo se midió</h2>
  <div class="cadena">focos VIIRS S-NPP, 7 días (NASA FIRMS)
  └─ confianza ≥ nominal          descarta reflejos y antorchas
  └─ dentro de Manantay           {foc['en_distrito']} focos
  └─ DBSCAN ≤ 1 km y ≤ 48 h       {foc['incendios_detectados']} incendios distintos
       └─ el mayor: {inc['n_focos']} focos, {n(inc['frp_total_mw'], 0)} MW, {inc['horas_activo']:.0f} h activo

Sentinel-2 L2A (Microsoft Planetary Computer)
  └─ candidatas listadas con fecha y nubosidad ANTES de calcular
  └─ elegida por nube sobre el recorte (SCL), no sobre la escena
  └─ NBR = (B08 − B12) / (B08 + B12)
  └─ dNBR = NBR_antes − NBR_después
       └─ umbral {area['umbral_dnbr']}             {n(area['hectareas'])} ha

cruces sobre la misma máscara
  └─ ESA WorldCover 10 m          qué se quemó
  └─ WorldPop 1 km, anillo 5 km   {n(exp['poblacion_5km_worldpop2020'])} personas
  └─ Open Buildings, anillo 1 km  {n(exp['edificaciones_1km_openbuildings'])} edificaciones</div>
  <p class="nota">Todas las fuentes son públicas y ninguna pide clave ni pago.
  El análisis corre en CPU.</p>

  <h2>Lo que estos números no dicen</h2>
  <ol class="limites">
    <li><strong>Un foco de calor no es un incendio.</strong> VIIRS detecta anomalías
    térmicas: quemas agrícolas controladas, hornos ladrilleros y fuegos forestales
    entran al mismo conteo.</li>
    <li><strong>Las nubes esconden el fuego.</strong> Quedó utilizable el
    {img['pixeles_utilizables_pct']} % de los píxeles; lo tapado no entra al área
    quemada. Las {n(area['hectareas'])} ha son un piso, no una estimación insesgada.</li>
    <li><strong>El umbral es una decisión, no un dato.</strong> Ver la tabla de arriba.</li>
    <li><strong>WorldCover es de 2021</strong> y subestima agricultura y construcción
    en un frente agrícola activo.</li>
    <li><strong>Una edificación no es una vivienda.</strong> Open Buildings detecta
    techos —galpones, colegios, corrales cuentan igual— y su cobertura cae en bosque
    denso. El conteo de expuestas es, otra vez, un piso.</li>
  </ol>

  <p class="pie-pagina">Alexander Noblejas · Ciencia de Datos con Python,
  Diplomatura QLAB · 21 de octubre de 2026.<br>
  Datos: NASA FIRMS · Sentinel-2 L2A y ESA WorldCover vía Microsoft Planetary
  Computer · WorldPop 2020 · Google Open Buildings v3 · límites INEI (UBIGEO).</p>
</div>
"""

destino = RAIZ / "outputs" / "dashboard.html"
destino.write_text(HTML, encoding="utf-8")
print(f"dashboard.html escrito · {len(HTML):,} bytes")
