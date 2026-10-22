# Fuego en Manantay · Ucayali, octubre 2026

**Ciencia de Datos con Python — Diplomatura QLAB · Alexander Noblejas**

Corte de datos: **2026-10-22 02:07 UTC**

Trabajo académico. No reemplaza los reportes del COEN, INDECI, SERFOR ni SERNANP.

---

## La pregunta

**¿Cuánto se quemó en Manantay, qué se quemó, a cuántas viviendas llegó — y es esta
semana de octubre excepcional frente a 2012–2025?**

Manantay es uno de los cuatro distritos de Pucallpa (Coronel Portillo,
Ucayali, UBIGEO 250107). Es periurbano: ciudad al norte,
chacra y bosque secundario al sur. El fuego ahí no cae sobre territorio vacío, y esa es
la razón de elegirlo.

El trabajo junta cuatro de los retos propuestos: **A** (cuánto se quemó, con dNBR),
**C** (qué se quemó, con WorldCover), **D** (a quién afectó, con WorldPop y Google Open
Buildings) y **E** (¿año récord?, con la serie FIRMS 2012–2025).

---

## Tres hallazgos

**1 · Se quemaron 892 hectáreas.** dNBR ≥ 0.27
entre el 2026-09-21 y el 2026-10-16, con el
**89.0 %** del área de interés utilizable (el resto quedó
bajo nube en alguna de las dos fechas). El incendio concentró 51 focos
VIIRS y 644 MW de energía radiativa acumulada, activo
36 horas. Para contraste, la huella VIIRS —el proxy operativo,
que **no** es área quemada— daba 1,133 ha.

**2 · Lo que ardió fue sobre todo pastizal:**
656 ha, el 74 % de la superficie quemada.

**3 · 35 edificaciones
quedaron a menos de 1000 m del fuego**
(0.2 ha construidas), en un entorno donde WorldPop estima
49,363 personas a
5 km. Este conteo es lo que agrega el trabajo:
WorldPop da personas por celda de 1 km; Open Buildings da un polígono por techo.

### Y el contexto: ¿es excepcional?

En la **misma ventana calendario** (12-10 + 10 días) comparada
año por año, 2026 registra **3,907 focos** frente a un promedio
2012–2025 de **2,616**: **+49 %**.

Pero **2026 no es el año récord**: es el puesto **2 de
15**, detrás de **2024**, que en esta misma ventana registró
5,345 focos. La respuesta honesta al reto «¿año récord?» es que no: la
temporada está claramente por encima de lo normal, y aun así hubo un octubre peor hace
2 años.

15 de 25 departamentos
están por encima de su propio promedio, y la mayor anomalía absoluta es
**Ucayali** (+411 focos sobre su promedio
de 524, z = +1.34).

Esta semana, Ucayali es el departamento con más focos del
país (791 de 4,380), y Manantay es el
distrito **#6** del Perú por energía liberada, entre
449 distritos con fuego.

---

## Los datos y sus fechas

| Dato | Fuente | Fecha / ventana | Tipo |
|---|---|---|---|
| Focos recientes | NASA FIRMS, VIIRS S-NPP (CSV 7 días) | 2026-10-14 → 2026-10-21 | Puntos |
| Serie histórica | NASA FIRMS, `VIIRS_SNPP_SP` por área | 12-10 + 10 días, 2012–2025 | Puntos |
| Imagen antes | Sentinel-2 L2A (Planetary Computer) | 2026-09-21 | Raster 20 m |
| Imagen después | Sentinel-2 L2A (Planetary Computer) | 2026-10-16 | Raster 20 m |
| Cobertura del suelo | ESA WorldCover (Planetary Computer) | 2021 | Raster 10 m |
| Población | WorldPop ajustado a ONU | 2020 | Raster 1 km |
| Edificaciones | Google Open Buildings v3 | — | Polígonos |
| Límites distritales | INEI / UBIGEO (`juaneladio/peru-geojson`) | — | Polígonos |

Ninguna fuente pide pago. La única que pide clave es FIRMS, y se lee de `.env`
(ver `.env.example`); nunca está en el código. Todo corre en CPU.

> **Aviso de comparabilidad.** 2012-2025 de VIIRS_SNPP_SP (archivo reprocesado); 2026 de VIIRS_SNPP_NRT (tiempo casi real). Mismo satélite, distinto procesamiento. El NRT no está revalidado, así que
> parte de la diferencia observada puede venir del procesamiento y no del fuego.

---

## El método

```
focos VIIRS S-NPP, 7 días (FIRMS)
  └─ confianza ≥ nominal                 descarta reflejos y fuentes fijas
  └─ sjoin con distritos (EPSG:4326)     4,380 focos → 449 distritos con fuego
  └─ DBSCAN ≤ 1 km y ≤ 48 h              86 focos en Manantay → 15 incendios
       └─ prioridad = log(1+FRP) × log(1+huella) × (1 + focos 24 h)
       └─ el de mayor FRP + margen 2 km  → área de interés

serie histórica, MISMA ventana calendario en cada año
  └─ años sin cobertura: se excluyen y se avisa, no se rellenan
  └─ por departamento: promedio, mediana, máximo, σ, z y puesto en su serie

Sentinel-2 L2A, grilla común UTM 18S a 20 m
  └─ candidatas listadas con fecha, nubes de escena y % inválido sobre el AOI
  └─ se elige por el % inválido sobre el AOI (SCL), NO por eo:cloud_cover
  └─ inspección previa: CRS, tamaño, bandas, nodata, dtype, extensión, válidos
  └─ assert misma_grilla() antes de restar
  └─ NBR = (B08 − B12)/(B08 + B12);  dNBR = NBR_antes − NBR_después
       └─ umbral 0.27  →  892 ha

cruces sobre la misma máscara de quemado
  └─ ESA WorldCover con like= la escena   misma grilla, nearest-neighbor
  └─ WorldPop, anillo 5 km                 49,363 personas
  └─ Open Buildings, anillo 1000 m        35 edificaciones
```

Todo en [`notebooks/incendios_manantay.ipynb`](notebooks/incendios_manantay.ipynb);
las fuentes, en [`src/datos.py`](src/datos.py).


> ⚠ **La imagen posterior es del mismo día en que el incendio seguía detectándose.** La toma captura el fuego en curso, así que lo que ardió después no aparece: la cifra de hectáreas es un piso adicional por esta razón, además de por las nubes. Es la misma salvedad que el ejemplo de clase marcó como «fuego activo».

### Las imágenes candidatas, con su nubosidad

Las dos cifras son distintas y por eso se reportan las dos: la de la escena cubre
110 × 110 km, la del AOI es la que de verdad afecta al incendio.

| Fecha | Nubes de la escena | Inválidos sobre el AOI |
|---|---:|---:|
| 1791849600 | 69.6 % | 100.0 % |
| 1791676800 | 39.0 % | 26.2 % |
| 1791244800 | 28.1 % | 17.8 % |
| 1790985600 | 39.6 % | 25.9 % |
| 1790812800 | 100.0 % | 100.0 % |
| 1790380800 | 96.4 % | 100.0 % |
| 1790121600 | 59.8 % | 68.3 % |
| 1789948800 | 1.1 % | 1.2 % |
| 1792108800 | 7.9 % | 9.9 % |
| 1792540800 | 94.7 % | 66.5 % |

### Hectáreas por severidad

| Clase | dNBR | Hectáreas |
|---|---:|---:|
| Rebrote | −∞ – -0.10 | 212 |
| Sin cambio | -0.10 – 0.10 | 6,153 |
| Severidad baja | 0.10 – 0.27 | 1,503 |
| Severidad moderada-baja | 0.27 – 0.44 | 584 |
| Severidad moderada-alta | 0.44 – 0.66 | 305 |
| Severidad alta | 0.66 – +∞ | 3 |

Umbrales de Key & Benson (USGS). **No son universales**: dependen del ecosistema, del
sensor, de las fechas y de una validación de campo que acá no existe. Son configurables
en la primera celda del notebook.

### El número depende del umbral

| Umbral | Hectáreas |
|---|---:|
| dNBR ≥ 0.10 | 2,394 |
| dNBR ≥ 0.27  ← **el nuestro** | 891 |
| dNBR ≥ 0.44 | 307 |
| dNBR ≥ 0.66 | 3 |

### Qué se quemó

| Cobertura (WorldCover 2021) | Hectáreas | % |
|---|---:|---:|
| Pastizal | 656 | 73.5 % |
| Bosque | 215 | 24.1 % |
| Humedal herbáceo | 20 | 2.2 % |
| Matorral | 1 | 0.1 % |
| Agua | 0 | 0.0 % |
| Área construida | 0 | 0.0 % |

### Departamentos que explican la anomalía

| Departamento | 2026 | Prom. 12–25 | Dif. | Var. % | z | Puesto en su serie |
|---|---:|---:|---:|---:|---:|---:|
| Ucayali | 935 | 524.4 | +411 | +78 % | +1.3 | 2 / 15 |
| Junin | 460 | 215.0 | +245 | +114 % | +3.0 | 1 / 15 |
| Ancash | 187 | 27.1 | +160 | +591 % | +6.9 | 1 / 15 |
| Apurimac | 217 | 60.1 | +157 | +261 % | +1.2 | 2 / 15 |
| Cusco | 291 | 150.4 | +141 | +94 % | +1.5 | 2 / 15 |
| Huanuco | 402 | 284.4 | +118 | +41 % | +0.9 | 4 / 15 |
| Arequipa | 131 | 31.9 | +99 | +310 % | +4.7 | 1 / 15 |
| Huancavelica | 112 | 40.1 | +72 | +180 % | +1.8 | 2 / 15 |
| Moquegua | 81 | 21.1 | +60 | +284 % | +3.6 | 1 / 15 |
| Puno | 120 | 68.7 | +51 | +75 % | +1.2 | 3 / 15 |

---

## El mapa

- [`outputs/dashboard.html`](outputs/dashboard.html) — el tablero para presentar.
- [`outputs/mapa_manantay.html`](outputs/mapa_manantay.html) — focos VIIRS con hora y
  FRP, huella proxy, perímetro distrital, anillo de 1000 m y fondo
  satelital.
- `figuras/` — focos por departamento, serie histórica, anomalía departamental, NBR/dNBR,
  área quemada, qué se quemó y edificaciones expuestas.

---

## Limitaciones

1. **Un foco de calor no es un incendio.** VIIRS detecta anomalías térmicas: quemas
   agrícolas controladas, hornos ladrilleros y fuegos forestales entran al mismo conteo.
   Separarlos exige información de campo que no tenemos.
2. **La huella VIIRS no es área quemada.** Es el buffer del píxel de 375 m, un proxy
   operativo. Se reporta aparte (1,133 ha) del dNBR
   (892 ha) justamente para no confundirlos.
3. **Las nubes esconden el fuego.** Quedó utilizable el
   89.0 % del AOI. Lo tapado no entra al área quemada, así
   que 892 ha es un **piso**, no una estimación insesgada. En la
   Amazonía en octubre, este es el sesgo dominante.
4. **El umbral es una decisión, no un dato.** Ver la tabla de sensibilidad.
5. **La serie histórica mezcla procesamientos** (SP para 2012–2025, NRT para 2026).
   Mismo satélite, distinta validación. Ningún año faltante se rellena.
6. **Una edificación no es una vivienda**, y WorldCover es de 2021. Open Buildings
   detecta techos —galpones, colegios y corrales cuentan igual—, su cobertura cae en
   bosque denso, y la cobertura del suelo tiene cinco años de desfase. Los dos sesgos van
   hacia abajo, justo en los territorios que más interesan.
7. **El dNBR mide un cambio, no una causa.** Una cosecha o un desmonte entre las dos
   fechas produce la misma caída del índice que el fuego. Lo que ata el cambio al
   incendio es que coincide espacialmente con los focos VIIRS, no el índice por sí solo.

---

## Instalación y ejecución

```bash
pip install -r requirements.txt
cp .env.example .env          # y pon tu clave de FIRMS
```

En Windows basta doble clic en `EJECUTAR.bat`. Manualmente:

```bash
python scripts/probar_fuentes.py                      # 2 min: verifica las 7 fuentes
jupyter nbconvert --execute --inplace     notebooks/incendios_manantay.ipynb                # el análisis completo
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
