# Alcance de seguridad

Este es un prototipo local con datos ficticios. El servidor usa `http.server` de Python, que [Python no recomienda para producción](https://docs.python.org/3/library/http.server.html). Solo escucha en `127.0.0.1`; no tiene opción de abrirse a otras interfaces. No habilitar túneles ni exponerlo a Internet como está.

## Controles implementados

- Identidad determinada por una clave aleatoria de 256 bits, almacenada como hash SHA-256 en SQLite. Ningún nombre, `actor_id` o rol del cuerpo puede suplantar al emisor.
- Clave por cuenta, miembros por sala, agentes sin rol de aprobación ni capacidad de crear salas. Agentes de la demo de solo lectura.
- Revocación comprobada en cada llamada, incluso antes de devolver una repetición idempotente. No revierte información ya leída.
- Stock estructurado, catálogo y origen ficticios, destino tomado de la sala, cantidad entera, separación solicitante/aprobador y revisión del hash exacto. Ninguna ruta ejecuta stock.
- Transacciones `BEGIN IMMEDIATE` e idempotencia por identidad/ruta/clave. Reusar una clave con contenido distinto da conflicto. La respuesta persistida permite resolver una confirmación perdida sin repetir la operación.
- Mensajes tratados como texto; renderizado con `textContent`. Sin Markdown activo, HTML, código, URLs ejecutables ni interpretación de instrucciones como aprobaciones.
- Una respuesta por agente/pedido humano dirigido, una contribución por colaborador/encargo, una síntesis por coordinador, vencimientos y máximo de cuatro colaboradores. Ningún agente crea nuevas rondas.
- Host y Origin de loopback, sin CORS, bearer en encabezado, CSP, protección de marcos, `no-store`, tamaño de cuerpo limitado y límite local de 240 llamadas/minuto. Credenciales ausentes de logs y respuestas.
- Auditoría de mutaciones aceptadas con actor, acción, objetivo, sala, fecha y hashes; comprobación de cadena y triggers contra modificación/borrado. Mensajes y datos se guardan por separado. No se registran todos los intentos rechazados ni cada lectura.

## Fronteras y límites

La persona con acceso al archivo SQLite o a la CLI es administradora de confianza: puede crear identidades o alterar la base. La cadena detecta alteraciones simples; no es almacenamiento inmutable ante ese administrador, ni demuestra autenticidad de una identidad real. Reescribir toda la cadena o eliminar su sufijo puede eludir la verificación sin un anclaje externo. No llamar a esto “auditoría inviolable”.

La demo genera archivos de claves con permisos 0600 en un directorio privado ignorado por Git. No publicarlos ni entregar una clave humana a un conector. En navegador la clave vive en memoria; no se guarda en cookies ni almacenamiento web. No hay recuperación, caducidad automática de credenciales ni rotación implementada: revocar y crear una identidad nueva. Personas distintas se prueban en pestañas separadas.

El contenido de sala es visible a sus miembros, incluidos agentes asignados. Un destino explícito decide qué pedido entra a su bandeja; no transforma el resto de la sala en una conversación privada. No existe búsqueda en conversaciones personales de Muse ni un token de Meta en este proyecto.

La autorización de la sala solo gobierna su API. **No puede controlar las acciones que un Muse real ejecute usando otros conectores privados.** Para una futura conexión, el propietario debe revisar su política de permisos y el ensayo debe limitarse a lectura/respuesta sobre datos sintéticos. Una guía escrita no sustituye controles verificables en el agente y en los sistemas destino.

La idempotencia requiere conservar la misma clave. La interfaz conserva claves pendientes mientras la pestaña permanece abierta. Si se cierra o recarga durante un resultado incierto, revisar el historial antes de volver a enviar. La igualdad semántica de dos mensajes con claves distintas no se considera duplicación.

No se adjuntan credenciales reales, cookies, tokens de proveedores, dumps de stock ni datos personales del personal. La cuenta “Parker · demo” es una identidad ficticia de ensayo.

## Trabajo pendiente para uso real

Servidor de producción, HTTPS, login y sesiones seguras de personas, cuotas por cuenta, rotación, verificación de propiedad de agentes, invitaciones/retiro de miembros, recuperación, retención/borrado con política definida, copias cifradas, registro de accesos y denegaciones, exportación/anclaje de auditoría y paginación de encargos/stock. Antes de ejecución real se requiere además un gateway que aplique permisos por acción y un destino con idempotencia y conciliación.
