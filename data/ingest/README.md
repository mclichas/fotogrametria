# Ingesta de datos

Colocar aquí **los videos y fotografías originales** de obra. Esta carpeta es la
única fuente de verdad; el pipeline nunca modifica ni renombra estos archivos.

## Convención de nombres

```text
AAAAMMDD-HHMMSS_<descripcion>.<ext>

20261005-081530_bano_principal.mp4
20261005-094210_bano_principal_detalle_01.mp4
```

* `AAAAMMDD-HHMMSS` — hora local de grabación/captura.
* `<descripcion>` — `snake_case`, sin espacios ni acentos.
* Extensiones admitidas: `.mp4`, `.mov`, `.avi`, `.mkv`, `.jpg`, `.jpeg`, `.png`, `.tif`.

## Notas

* Todo lo generado (frames extraídos, COLMAP, nubes de puntos, intermedios) va a `work/`.
* Los entregables finales (`floor_plan_3d.svg` en V1, `metrics_report.json`) van a `outputs/`.
* Esta carpeta vive en la **carpeta de Google Drive de la cuenta dedicada del proyecto**
  (D10/AGENTS.md); la carga es manual por el navegador. El pipeline no modifica ni
  renombra estos originales.
* Borrar `work/` no pierde datos: sólo descarta el progreso de reconstrucción.