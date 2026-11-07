# Incremento D — manifiestos de empaquetado webOS

Cada directorio `apps/<name>/` contiene dos archivos distintos:

- `appinfo.json`: metadatos oficiales de webOS que sí se incluyen en el IPK.
- `manifest.json`: metadatos **locales de construcción** que se validan antes de
  empaquetar y se excluyen del staging.

## Esquema v1

```json
{
  "schema": "gway-webos-tv/app-build/v1",
  "entry": "index.html",
  "bridge": {
    "mode": "inject",
    "file": "app.js",
    "config_key": "bridge_url"
  }
}
```

Para aplicaciones que no usan bridge: `"bridge": {"mode": "none"}`.
`entry` debe coincidir con `appinfo.json.main`. `file` debe ser un
archivo JavaScript local con exactamente una ocurrencia del punto de inyección
WSS existente. No se permiten rutas absolutas, traversal ni enlaces simbólicos.
La configuración WSS procede de `--config` o de la ruta XDG preexistente;
no se incluyen credenciales ni el archivo de configuración en el IPK.

## Comandos compatibles

```sh
python scripts/tv-app.py remote-test --config ~/.config/gway-webos-tv/app-build.json
python scripts/tv-app.py gway-monitor --config ~/.config/gway-webos-tv/app-build.json
python scripts/tv-app.py all --config ~/.config/gway-webos-tv/app-build.json
```

`all` descubre automáticamente los directorios con `manifest.json`.
Sin argumentos se conserva el valor predeterminado `remote-test`.
`--replace`, `--check`, `--install`, `--launch`, `--device`,
`--host` y `--output-dir` mantienen su semántica previa.
`--install` requiere comprobación del dispositivo emparejado.

## Añadir otra aplicación

Crear `apps/new-app/` con `appinfo.json`, `index.html` y
`manifest.json`. Si no necesita WSS, utilizar `mode: none`; no es
necesario modificar `scripts/tv-app.py`.

## Pruebas y rollback

`tests/test_webos_manifest.py` valida descubrimiento, tercera app,
inyección, staging, construcción conjunta simulada y manifiestos inválidos.
`tests/test_monitor_packaging.py` conserva la regresión de monitor.
El CI debe pasar en Python 3.11 y 3.13 antes de fusionar.

La construcción simulada prueba la lógica del empaquetador pero no sustituye
un build real con `ares-package` ni la instalación en un televisor.
Para rollback, revertir esta PR; los paquetes instalados previamente no
se modifican automáticamente.
