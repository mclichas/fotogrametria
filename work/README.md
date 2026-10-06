# work/ — intermedios generados (Drive, D10)

Carpeta desechable del pipeline. Vive en la carpeta compartida de Google Drive
(D10), **NO** en el repo. Se regenera desde `data/ingest/` y se puede borrar sin
perder nada original.

Contenido por `source_id`:

* `work/<source_id>/frames/` — frames extraídos (jpg)
* `work/<source_id>/session.json` — estado del wizard, resumible por paso (§12)

Regla de higiene (§2.3): se mantienen originales + entregables + `session.json`;
los intermedios pesados (nubes, matches, máscaras) se limpian al exportar.

**No se versiona en GitHub** (repo público, T11): ni frames, ni nubes, ni
videos. El repo solo guarda este README como resguardo de la estructura.