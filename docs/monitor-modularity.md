# Incremento B — registros y compatibilidad

Esta implementación corresponde al issue #13 y a la PR #14.

## Backend

`monitor.snapshot` sigue entregando `type`, `observed_at` y los cinco namespaces:
`hardware`, `ocpp`, `github`, `deployments`, `fleet`.
`monitor.PROVIDERS` define el orden y `provider_registry()` resuelve los colectores.
`monitor_sources.py` conserva los fallbacks de red y las consultas de transacciones.
`collect_providers()` acepta un diccionario opcional de colectores para pruebas y
extensiones controladas. Un fallo de proveedor devuelve un estado de indisponibilidad
sin exponer el texto de la excepción. `metrics` registra latencia por proveedor
**solo en el proceso servidor**, nunca en el payload del TV.

Los subprocess tienen límites individuales existentes (12 s para consultas JSON,
5 s por repositorio GitHub), pero **no hay deadline total** del snapshot.
No se promete cancelación de llamadas bloqueadas ni concurrencia.

## Frontend

`channel-registry.js` se carga antes de `app.js` como script clásico, sin
transpilación, y valida IDs, referencias DOM y renderizadores. El registro permite
agregar un sexto canal declarando su vista y descriptor, sin editar la fórmula
de navegación ni el despacho de render. Los cinco renderizadores actuales permanecen
en `app.js`; moverlos a archivos propios corresponde al incremento C.

La aplicación conserva el endpoint de inyección WSS utilizado por
`scripts/tv-app.py`, los IDs de DOM y los controles PageUp/PageDown, Up/Down,
OK para pairing, reconexión y freshness. Los permisos siguen en el bridge,
no en descriptores del frontend.

## Verificación B4

- `tests/test_monitor.py`: contrato existente Hardware/OCPP, fallback y ausencia.
- `tests/test_monitor_providers.py`: cinco namespaces, sexto proveedor,
  métricas, validación y aislamiento.
- `tests/test_monitor_characterization.py`: separación de capabilities
  y caché del bridge.
- `tests/test_monitor_frontend.py`: script order, canal adicional, navegación
  circular y validación mediante Node cuando esté disponible.
- `tests/test_monitor_packaging.py`: staging de IPK simulado, inyección WSS,
  fuente original intacta.
- `tests/test_event_bridge.py`: integración TLS/pairing preexistente.

Ejecutar `python -m pytest` y `python -m build` en CI; verificar el resultado
antes de fusionar. El test con Node se omite si no está instalado.
La aceptación física de INFO/SAP y botones del control remoto requiere TV
real; no se puede sustituir con mocks ni afirmar verificación física.
No desplegar a TV desde esta PR.

## Rollback

Revertir la PR y volver a empaquetar la versión previa. No modificar credenciales,
pairing ni el almacenamiento local del televisor.
