"""
Escribe el README a partir de outputs/hallazgos.json.

Ninguna cifra del README se escribe a mano: todas salen de la corrida. Si
vuelves a correr el notebook con otras fechas u otro umbral, el README se
actualiza solo.

    python scripts/render_readme.py
"""

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
H = json.loads((RAIZ / "outputs" / "hallazgos.json").read_text(encoding="utf-8"))

nac, his, inc = H["nacional"], H["historico"], H["incendio"]
img, area, exp = H["imagenes"], H["area_quemada"], H["exposicion"]
cob = [c for c in H["que_se_quemo"] if c["hectareas"] > 0]
principal = cob[0] if cob else {"clase": "—", "hectareas": 0, "pct": 0}
lider = his["mayor_anomalia"]

n = lambda v, d=0: f"{v:,.{d}f}"


def tabla(filas, cols, alinea_num=True):
    cab = "| " + " | ".join(c[0] for c in cols) + " |"
    sep = "|" + "|".join("---:" if (alinea_num and i) else "---"
                         for i, _ in enumerate(cols)) + "|"
    cuerpo = "\n".join(
        "| " + " | ".join(c[1](f) for c in cols) + " |" for f in filas)
    return f"{cab}\n{sep}\n{cuerpo}"


severidad = tabla(
    [s for s in area["por_severidad"] if s["hectareas"] > 0],
    [("Clase", lambda s: s["clase"]),
     ("dNBR", lambda s: f"{s['dnbr_min']:.2f} – {s['dnbr_max']:.2f}"
      .replace("-inf", "−∞").replace("inf", "+∞")),
     ("Hectáreas", lambda s: n(s["hectareas"]))])

sens = tabla(
    area["sensibilidad_umbral"],
    [("Umbral", lambda s: f"dNBR ≥ {s['umbral dNBR']:.2f}"
      + ("  ← **el nuestro**" if abs(s["umbral dNBR"] - area["umbral_dnbr"]) < 1e-9
         else "")),
     ("Hectáreas", lambda s: n(s["hectáreas"]))])

cobertura = tabla(
    cob[:8],
    [("Cobertura (WorldCover 2021)", lambda c: c["clase"]),
     ("Hectáreas", lambda c: n(c["hectareas"])),
     ("%", lambda c: f"{c['pct']:.1f} %")])

deptos = tabla(
    his["por_departamento"][:10],
    [("Departamento", lambda d: d["departamento"].title()),
     ("2026", lambda d: n(d["focos_2026"])),
     ("Prom. 12–25", lambda d: n(d["promedio"], 1)),
     ("Dif.", lambda d: f"{d['diferencia']:+,.0f}"),
     ("Var. %", lambda d: "—" if d.get("variacion_pct") is None
      else f"{d['variacion_pct']:+,.0f} %"),
     ("z", lambda d: "—" if d.get("z") is None else f"{d['z']:+.1f}"),
     ("Puesto en su serie", lambda d: f"{d['puesto_en_su_serie']} / "
      f"{d['de_n_anios']}")])

candidatas = tabla(
    img["candidatas_antes"] + img["candidatas_despues"],
    [("Fecha", lambda c: str(c["fecha"])[:10]),
     ("Nubes de la escena", lambda c: "—" if c.get("nubes_escena_pct") is None
      else f"{c['nubes_escena_pct']:.1f} %"),
     ("Inválidos sobre el AOI", lambda c: f"{c['invalidos_aoi_pct']:.1f} %")])

aviso_anios = ""
if his["anios_faltantes"]:
    aviso_anios = (f"\n> ⚠ Años sin cobertura comparable, excluidos del cálculo y "
                   f"**no rellenados**: {', '.join(map(str, his['anios_faltantes']))}.\n")

README = f"""# Fuego en Manantay · Ucayali, octubre 2026

**Ciencia de Datos con Python — Diplomatura QLAB · Alexander Noblejas**

Corte de datos: **{H['corte']}**

Trabajo académico. No reemplaza los reportes del COEN, INDECI, SERFOR ni SERNANP.

---

## La pregunta

**¿Cuánto se quemó en Manantay, qué se quemó, a cuántas viviendas llegó — y es esta
semana de octubre excepcional frente a 2012–2025?**

Manantay es uno de los cuatro distritos de Pucallpa ({H['provincia'].title()},
{H['departamento'].title()}, UBIGEO {H['ubigeo']}). Es periurbano: ciudad al norte,
chacra y bosque secundario al sur. El fuego ahí no cae sobre territorio vacío, y esa es
la razón de elegirlo.

El trabajo junta cuatro de los retos propuestos: **A** (cuánto se quemó, con dNBR),
**C** (qué se quemó, con WorldCover), **D** (a quién afectó, con WorldPop y Google Open
Buildings) y **E** (¿año récord?, con la serie FIRMS 2012–2025).

---

## Tres hallazgos

**1 · Se quemaron {n(area['hectareas'])} hectáreas.** dNBR ≥ {area['umbral_dnbr']}
entre el {img['antes']['fecha']} y el {img['despues']['fecha']}, con el
**{img['pixeles_utilizables_pct']} %** del área de interés utilizable (el resto quedó
bajo nube en alguna de las dos fechas). El incendio concentró {inc['n_focos']} focos
VIIRS y {n(inc['frp_total_mw'])} MW de energía radiativa acumulada, activo
{inc['horas_activo']:.0f} horas. Para contraste, la huella VIIRS —el proxy operativo,
que **no** es área quemada— daba {n(inc['huella_viirs_ha'])} ha.

**2 · Lo que ardió fue sobre todo {principal['clase'].lower()}:**
{n(principal['hectareas'])} ha, el {principal['pct']:.0f} % de la superficie quemada.

**3 · {n(exp['edificaciones_1km_openbuildings'])} edificaciones quedaron a menos de
{exp['radio_viviendas_m']} m del fuego** ({n(exp['ha_construidas_1km'], 1)} ha
construidas), en un entorno donde WorldPop estima
{n(exp['poblacion_5km_worldpop2020'])} personas a {exp['radio_poblacion_m'] // 1000} km.
Este conteo es lo que agrega el trabajo: WorldPop da personas por celda de 1 km;
Open Buildings da un polígono por techo.

### Y el contexto: ¿es excepcional?

En la **misma ventana calendario** ({his['ventana_calendario']}) comparada año por año,
2026 registra **{n(his['focos_2026'])} focos** frente a un promedio 2012–2025 de
**{n(his['promedio_2012_2025'], 0)}**: **{his['variacion_pct']:+.0f} %**, el puesto
**{his['puesto_2026']} de {his['de_n_anios']}** años de la serie.
{his['departamentos_sobre_su_promedio']} de {his['de_n_departamentos']} departamentos
están por encima de su propio promedio, y la mayor anomalía absoluta es
**{lider['departamento'].title()}** ({lider['diferencia']:+,.0f} focos sobre su promedio
de {n(lider['promedio'], 0)}).
{aviso_anios}
Esta semana, {nac['departamento_mas_focos'].title()} es el departamento con más focos del
país ({n(nac['focos_ese_departamento'])} de {n(nac['focos_7d'])}), y Manantay es el
distrito **#{nac['puesto_manantay']}** del Perú por energía liberada, entre
{n(nac['distritos_con_fuego'])} distritos con fuego.

---

## Los datos y sus fechas

| Dato | Fuente | Fecha / ventana | Tipo |
|---|---|---|---|
| Focos recientes | NASA FIRMS, VIIRS S-NPP (CSV 7 días) | {nac['ventana'][0][:10]} → {nac['ventana'][1][:10]} | Puntos |
| Serie histórica | NASA FIRMS, `VIIRS_SNPP_SP` por área | {his['ventana_calendario']}, 2012–2025 | Puntos |
| Imagen antes | Sentinel-2 L2A (Planetary Computer) | {img['antes']['fecha']} | Raster {img['resolucion_m']} m |
| Imagen después | Sentinel-2 L2A (Planetary Computer) | {img['despues']['fecha']} | Raster {img['resolucion_m']} m |
| Cobertura del suelo | ESA WorldCover (Planetary Computer) | 2021 | Raster 10 m |
| Población | WorldPop ajustado a ONU | 2020 | Raster 1 km |
| Edificaciones | Google Open Buildings v3 | — | Polígonos |
| Límites distritales | INEI / UBIGEO (`juaneladio/peru-geojson`) | — | Polígonos |

Ninguna fuente pide pago. La única que pide clave es FIRMS, y se lee de `.env`
(ver `.env.example`); nunca está en el código. Todo corre en CPU.

> **Aviso de comparabilidad.** {his['aviso_sensores']} El NRT no está revalidado, así que
> parte de la diferencia observada puede venir del procesamiento y no del fuego.

---

## El método

```
focos VIIRS S-NPP, 7 días (FIRMS)
  └─ confianza ≥ nominal                 descarta reflejos y fuentes fijas
  └─ sjoin con distritos (EPSG:4326)     {n(nac['focos_7d'])} focos → {n(nac['distritos_con_fuego'])} distritos con fuego
  └─ DBSCAN ≤ 1 km y ≤ 48 h              {inc['focos_en_distrito']} focos en Manantay → {inc['incendios_en_distrito']} incendios
       └─ prioridad = log(1+FRP) × log(1+huella) × (1 + focos 24 h)
       └─ el de mayor FRP + margen 2 km  → área de interés

serie histórica, MISMA ventana calendario en cada año
  └─ años sin cobertura: se excluyen y se avisa, no se rellenan
  └─ por departamento: promedio, mediana, máximo, σ, z y puesto en su serie

Sentinel-2 L2A, grilla común UTM 18S a {img['resolucion_m']} m
  └─ candidatas listadas con fecha, nubes de escena y % inválido sobre el AOI
  └─ se elige por el % inválido sobre el AOI (SCL), NO por eo:cloud_cover
  └─ inspección previa: CRS, tamaño, bandas, nodata, dtype, extensión, válidos
  └─ assert misma_grilla() antes de restar
  └─ NBR = (B08 − B12)/(B08 + B12);  dNBR = NBR_antes − NBR_después
       └─ umbral {area['umbral_dnbr']}  →  {n(area['hectareas'])} ha

cruces sobre la misma máscara de quemado
  └─ ESA WorldCover con like= la escena   misma grilla, nearest-neighbor
  └─ WorldPop, anillo {exp['radio_poblacion_m'] // 1000} km                 {n(exp['poblacion_5km_worldpop2020'])} personas
  └─ Open Buildings, anillo {exp['radio_viviendas_m']} m        {n(exp['edificaciones_1km_openbuildings'])} edificaciones
```

Todo en [`notebooks/incendios_manantay.ipynb`](notebooks/incendios_manantay.ipynb);
las fuentes, en [`src/datos.py`](src/datos.py).

### Las imágenes candidatas, con su nubosidad

Las dos cifras son distintas y por eso se reportan las dos: la de la escena cubre
110 × 110 km, la del AOI es la que de verdad afecta al incendio.

{candidatas}

### Hectáreas por severidad

{severidad}

Umbrales de Key & Benson (USGS). **No son universales**: dependen del ecosistema, del
sensor, de las fechas y de una validación de campo que acá no existe. Son configurables
en la primera celda del notebook.

### El número depende del umbral

{sens}

### Qué se quemó

{cobertura}

### Departamentos que explican la anomalía

{deptos}

---

## El mapa

- [`outputs/dashboard.html`](outputs/dashboard.html) — el tablero para presentar.
- [`outputs/mapa_manantay.html`](outputs/mapa_manantay.html) — focos VIIRS con hora y
  FRP, huella proxy, perímetro distrital, anillo de {exp['radio_viviendas_m']} m y fondo
  satelital.
- `figuras/` — focos por departamento, serie histórica, anomalía departamental, NBR/dNBR,
  área quemada, qué se quemó y edificaciones expuestas.

---

## Limitaciones

1. **Un foco de calor no es un incendio.** VIIRS detecta anomalías térmicas: quemas
   agrícolas controladas, hornos ladrilleros y fuegos forestales entran al mismo conteo.
   Separarlos exige información de campo que no tenemos.
2. **La huella VIIRS no es área quemada.** Es el buffer del píxel de 375 m, un proxy
   operativo. Se reporta aparte ({n(inc['huella_viirs_ha'])} ha) del dNBR
   ({n(area['hectareas'])} ha) justamente para no confundirlos.
3. **Las nubes esconden el fuego.** Quedó utilizable el
   {img['pixeles_utilizables_pct']} % del AOI. Lo tapado no entra al área quemada, así
   que {n(area['hectareas'])} ha es un **piso**, no una estimación insesgada. En la
   Amazonía en octubre, este es el sesgo dominante.
4. **El umbral es una decisión, no un dato.** Ver la tabla de sensibilidad.
5. **La serie histórica mezcla procesamientos** (SP para 2012–2025, NRT para 2026).
   Mismo satélite, distinta validación. Ningún año faltante se rellena.
6. **Una edificación no es una vivienda**, y WorldCover es de 2021. Open Buildings
   detecta techos —galpones, colegios y corrales cuentan igual—, su cobertura cae en
   bosque denso, y la cobertura del suelo tiene cinco años de desfase. Los dos sesgos van
   hacia abajo, justo en los territorios que más interesan.

---

## Instalación y ejecución

```bash
pip install -r requirements.txt
cp .env.example .env          # y pon tu clave de FIRMS
```

En Windows basta doble clic en `EJECUTAR.bat`. Manualmente:

```bash
python scripts/probar_fuentes.py                      # 2 min: verifica las 7 fuentes
jupyter nbconvert --execute --inplace \
    notebooks/incendios_manantay.ipynb                # el análisis completo
python scripts/render_readme.py                       # regenera este README
python scripts/build_dashboard.py                     # regenera el tablero
```

## Estructura

```
src/datos.py          las ocho fuentes, cacheadas en data/
notebooks/            el análisis, de punta a punta
scripts/              pruebas de fuentes, README y tablero
outputs/              hallazgos.json, dashboard, mapa y CSVs
figuras/              los PNG del notebook
data/                 descargas (fuera de git)
```

## Outputs

| Archivo | Qué es |
|---|---|
| `outputs/hallazgos.json` | todas las cifras; el README y el tablero se generan de acá |
| `outputs/dashboard.html` | el tablero para presentar |
| `outputs/mapa_manantay.html` | mapa interactivo |
| `outputs/severidad.csv` | hectáreas por clase de severidad |
| `outputs/cobertura_quemada.csv` | hectáreas quemadas por cobertura |
| `outputs/anomalia_departamental.csv` | 2026 contra 2012–2025 por departamento |
| `outputs/ranking_distrital_7d.csv` | los 50 distritos con más FRP |
| `outputs/incendios_manantay.csv` | los incendios agrupados del distrito |
"""

(RAIZ / "README.md").write_text(README, encoding="utf-8")
print(f"README.md escrito · {len(README.splitlines())} líneas")
