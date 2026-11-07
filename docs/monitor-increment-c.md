# Incremento C — módulos del monitor webOS

La aplicación conserva el transporte WSS, el emparejamiento, el polling, el
reintento y la validación de freshness en `app.js`. Cada canal vive en
`channels/<id>.js` y se registra en `window.GwayMonitorChannels`.

## Contrato de canal

- `id`: ID de sección y sufijo de `tab-<id>`.
- `title`: título visible.
- `snapshotKey`: campo del payload `monitor.snapshot`.
- `render(payload)`: actualiza únicamente la vista del canal.
- `mount()` y `unmount()`: ciclo de vida al seleccionar o abandonar la vista.
- `onKey(code)` (opcional): devuelve `true` si consumió la tecla.

PageUp/PageDown, OK para pairing, credenciales y reconexión pertenecen al
núcleo. El registro valida ID, DOM, callbacks y snapshotKey. No se cargan
scripts externos ni se otorgan permisos por descriptor.

Los módulos usan scripts clásicos, sin bundler, aptos para Chromium 94.
`core/format.js` expone utilidades compartidas sin almacenar secretos.
La selección de tarjetas pertenece a GitHub, Deployments y Fleet.

## Orden de carga

`secret-dialog.js`, `core/format.js`, `channel-registry.js`,
los cinco scripts `channels/*.js` y, finalmente, `app.js`.

El punto de inyección WSS en `app.js` no cambia. `tv-app.py` copia todo el
árbol de `apps/gway-monitor` al staging, incluyendo los módulos nuevos.

## Verificación

`tests/test_monitor_increment_c.py` comprueba carga, cinco módulos,
render de ausencia, ciclo de vida, teclado y un sexto canal ficticio.
Las pruebas preexistentes comprueban pairing, bridge, proveedores, snapshot
e inyección WSS. El CI ejecuta pytest para Python 3.11/3.13 y build.

La prueba con Node no equivale a una validación física del control remoto
en webOS; realizar una comprobación manual antes del despliegue a clientes.
Rollback: revertir esta PR y volver a empaquetar la versión anterior.
