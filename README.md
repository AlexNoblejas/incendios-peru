# Incendios en Manantay, Ucayali · octubre 2026

**Ciencia de Datos con Python — Diplomatura QLAB · Alexander Noblejas**

> ⏳ **Números pendientes.** Corre `notebooks/incendios_manantay.ipynb` de arriba a
> abajo y luego `python scripts/render_readme.py`: este README se reescribe solo con
> las cifras reales de la corrida (hallazgos, fechas, nubosidad, umbral).

## La pregunta

**¿Cuánto se quemó en Manantay, qué se quemó y a cuántas viviendas llegó el fuego?**

Junta tres de los retos de la tarea: **A** (cuánto se quemó, con dNBR sobre
Sentinel-2), **C** (qué se quemó, con ESA WorldCover) y **D** (a quién afectó, con
WorldPop y **Google Open Buildings**).

## Reproducir

```bash
pip install -r requirements.txt
jupyter lab notebooks/incendios_manantay.ipynb
python scripts/render_readme.py
```

Ninguna fuente pide clave ni pago. Todo corre en CPU. Los datos se descargan solos
a `data/` (ignorada por git).
