"""
Escribe el README a partir de outputs/hallazgos.json.

Ninguna cifra del README se escribe a mano: todas salen de la corrida. Si vuelves
a correr el notebook con otras fechas u otro umbral, el README se actualiza solo.

    python scripts/render_readme.py
"""

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
H = json.loads((RAIZ / "outputs" / "hallazgos.json").read_text(encoding="utf-8"))

inc, img, area, exp = H["incendio"], H["imagenes"], H["area_quemada"], H["exposicion"]
cob = H["que_se_quemo"]
principal = cob[0] if cob else {"clase": "—", "hectareas": 0, "pct": 0}

sens = "\n".join(
    f"| dNBR ≥ {r['umbral dNBR']:.2f} | {r['hectáreas']:,.0f} ha |"
    for r in area["sensibilidad_umbral"])

cobertura = "\n".join(
    f"| {r['clase']} | {r['hectareas']:,.0f} | {r['pct']:.1f} % |"
    for r in cob[:6])

severidad = "\n".join(
    f"| {r['clase']} | {r['hectareas']:,.0f} |"
    for r in area["por_severidad"] if r["hectareas"] > 0)

README = f"""# Incendios en Manantay, Ucayali · octubre 2026

**Ciencia de Datos con Python — Diplomatura QLAB · Alexander Noblejas**

Corte de datos: {H['corte']}

Herramienta académica. No reemplaza los reportes del COEN, INDECI, SERFOR ni SERNANP.

---

## La pregunta

**¿Cuánto se quemó en Manantay, qué se quemó y a cuántas viviendas llegó el fuego?**

Manantay es uno de los cuatro distritos de Pucallpa ({H['provincia']}, {H['departamento']},
UBIGEO {H['ubigeo']}). Es periurbano: ciudad al norte, chacra y bosque secundario al
sur. El fuego ahí no cae sobre territorio vacío, y esa es la razón de la pregunta.

El trabajo junta tres de los retos propuestos: **A** (cuánto se quemó, con dNBR),
**C** (qué se quemó, con WorldCover) y **D** (a quién afectó, con WorldPop y
Google Open Buildings).

---

## Tres hallazgos

**1 · Se quemaron {area['hectareas']:,.0f} hectáreas** (dNBR ≥ {area['umbral_dnbr']},
imágenes del {img['antes']['fecha']} y el {img['despues']['fecha']}). El incendio
concentró {inc['n_focos']} focos VIIRS y {inc['frp_total_mw']:,.0f} MW de energía
radiativa acumulada, activo durante {inc['horas_activo']:.0f} horas.

**2 · Lo que ardió fue sobre todo {principal['clase'].lower()}**:
{principal['hectareas']:,.0f} ha, el {principal['pct']:.0f} % de la superficie quemada.

**3 · {exp['edificaciones_1km_openbuildings']:,} edificaciones quedaron a menos de
1 km del fuego** ({exp['ha_construidas_1km']:,.1f} ha construidas), dentro de un área
donde WorldPop estima {exp['poblacion_5km_worldpop2020']:,} personas a 5 km. El conteo
de edificaciones es lo que agrega este trabajo: WorldPop da personas por celda de
1 km, Open Buildings da un polígono por techo.

---

## Los datos y sus fechas

| Dato | Fuente | Fecha / ventana | Tipo |
|---|---|---|---|
| Focos de calor | NASA FIRMS, {H['focos']['sensor']} | {H['focos']['ventana'][0][:10]} a {H['focos']['ventana'][1][:10]} | Puntos (CSV) |
| Imagen antes | Sentinel-2 L2A (Planetary Computer) | {img['antes']['fecha']} · {img['antes']['nubes_recorte_pct']} % nubes sobre el recorte | Raster 20 m |
| Imagen después | Sentinel-2 L2A (Planetary Computer) | {img['despues']['fecha']} · {img['despues']['nubes_recorte_pct']} % nubes sobre el recorte | Raster 20 m |
| Cobertura del suelo | ESA WorldCover | 2021 | Raster 10 m |
| Población | WorldPop ajustado a ONU | 2020 | Raster 1 km |
| Edificaciones | Google Open Buildings v3 | — | Polígonos |
| Límites distritales | INEI / UBIGEO (peru-geojson) | — | Polígonos |

Entre las dos imágenes pasaron **{img['dias_entre']} días**, y quedó utilizable el
**{img['pixeles_utilizables_pct']} %** de los píxeles del recorte: el resto estuvo
bajo nube en alguna de las dos fechas.

Ninguna fuente pide clave ni pago. Todo corre en CPU.

---

## El método

```
focos VIIRS 7 días
   └─ filtro: confianza ≥ nominal        (descarta reflejos y antorchas)
   └─ sjoin con distritos                → focos dentro de Manantay
   └─ DBSCAN ≤ 1 km y ≤ 48 h             → {H['focos']['incendios_detectados']} incendios distintos
         └─ el de mayor FRP + margen 2 km → área de interés

Sentinel-2 L2A, antes y después
   └─ se listan TODAS las candidatas con fecha y nubosidad
   └─ se elige por nubes sobre el recorte (SCL), no por nubes de la escena
   └─ NBR = (B08 − B12)/(B08 + B12), enmascarado con SCL
   └─ dNBR = NBR_antes − NBR_después
         └─ umbral {area['umbral_dnbr']} (Key & Benson)  → hectáreas quemadas

cruces sobre la misma máscara de quemado
   └─ ESA WorldCover 10 m                → qué se quemó
   └─ WorldPop 1 km, anillo 5 km         → cuántas personas
   └─ Open Buildings, anillo 1 km        → cuántas edificaciones
```

Todo está en [`notebooks/incendios_manantay.ipynb`](notebooks/incendios_manantay.ipynb);
las fuentes de datos, en [`src/datos.py`](src/datos.py).

### Hectáreas por severidad

| Clase | Hectáreas |
|---|---:|
{severidad}

### El número depende del umbral

La misma imagen, cuatro umbrales:

| Umbral | Hectáreas |
|---|---:|
{sens}

Reportamos **{area['umbral_dnbr']}**. Los otros tres son el intervalo de lo defendible,
y se muestran justamente porque la computadora siempre da un número.

### Qué se quemó

| Cobertura (WorldCover 2021) | Hectáreas | % |
|---|---:|---:|
{cobertura}

---

## El mapa

[`outputs/mapa_manantay.html`](outputs/mapa_manantay.html) — focos VIIRS con hora y
FRP, perímetro del distrito, anillo de 1 km y fondo satelital.

También en `figuras/`: NBR antes y después, dNBR, superficie quemada, qué se quemó y
las edificaciones expuestas.

---

## Limitaciones

1. **Un foco de calor no es un incendio.** VIIRS detecta anomalías térmicas: quemas
   agrícolas controladas, hornos ladrilleros y fuegos forestales entran al mismo
   conteo. Separarlos exige información de campo que no tenemos.
2. **Las nubes esconden el fuego.** Quedó utilizable el {img['pixeles_utilizables_pct']} %
   de los píxeles. Lo tapado por nube no entra al área quemada, así que
   {area['hectareas']:,.0f} ha es un **piso**, no una estimación insesgada. En la
   Amazonía en octubre, este es el sesgo dominante.
3. **El umbral es una decisión, no un dato.** Ver la tabla de sensibilidad.
4. **WorldCover es de 2021 y el fuego de 2026.** Cinco años de frente agrícola en
   Ucayali desfasan la clasificación en una dirección conocida: subestima agricultura
   y construcción, sobreestima bosque.
5. **Una edificación no es una vivienda.** Open Buildings detecta techos: galpones,
   colegios y corrales cuentan igual que una casa, y su cobertura cae en bosque denso.
   El conteo de expuestas es, otra vez, un piso.

---

## Reproducir

```bash
pip install -r requirements.txt
jupyter lab notebooks/incendios_manantay.ipynb   # corre de arriba a abajo
python scripts/render_readme.py                  # regenera este README
```

Los datos se descargan solos a `data/` (ignorada por git) y se cachean.
"""

(RAIZ / "README.md").write_text(README, encoding="utf-8")
print(f"README.md escrito · {len(README.splitlines())} líneas")
