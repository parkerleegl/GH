# API local · v0.1

Base de desarrollo: `http://127.0.0.1:8765`. JSON UTF-8. Todas las rutas `/api/` requieren `Authorization: Bearer <clave_de_esta_identidad>`. No se aceptan credenciales por URL. Las páginas estáticas no contienen datos privados.

Cada `POST` requiere `Content-Type: application/json`, `Content-Length` y un `Idempotency-Key` de 8–128 caracteres (`A-Z`, `a-z`, dígitos, `_ . : -`). Repetir la misma ruta, identidad, clave y contenido devuelve el recibo original. Cambiar el contenido conservando la clave devuelve 409. Los campos desconocidos se rechazan; no aceptar `actor_id` ni roles dentro de un mensaje.

## Operaciones

| Método y ruta | Cuerpo / resultado | Permiso y efecto |
| --- | --- | --- |
| `GET /api/me` | ID, nombre, tipo y permisos propios | Lectura de identidad activa |
| `GET /api/rooms` | Array de salas de la identidad | Lectura |
| `GET /api/identities` | Array de identidades activas, sin claves | Solo persona administradora |
| `POST /api/rooms` | `name`, `site`, `members:[{id,role}]`; devuelve `id` | Administración humana. Crea sala. Creador es aprobador; no repetirlo en miembros. |
| `GET /api/rooms/{room}` | Nombre, local, rol propio, participantes, últimos 100 mensajes, solicitudes y encargos | Miembro de la sala. `integration:unverified`, `stock_execution:unavailable` |
| `GET /api/rooms/{room}/messages?after=0` | `items`, `next_cursor`; hasta 100 en orden de secuencia | Miembro. Cursor numérico exclusivo. |
| `GET /api/rooms/{room}/inbox?after=0` | Mensajes dirigidos pendientes y encargos asignados | Solo agente miembro. Lectura; no toma ni ejecuta trabajos. |
| `GET /api/rooms/{room}/audit?after=0` | Hasta 100 eventos en orden de `seq` | Miembro. Para seguir, pasar el último `seq`. |
| `POST /api/rooms/{room}/messages` | Persona: `text`, opcional `targets:[agent_id]`. Agente: `text`, `reply_to:message_id`. Devuelve `id`. | Persona miembro o agente con escritura habilitada. Publica un mensaje local. |
| `POST /api/rooms/{room}/requests` | `sku`, `quantity`, `note`; devuelve `id`, `status`, `executed:false` | Persona miembro. Crea solicitud ficticia; agentes denegados. |
| `POST /api/rooms/{room}/requests/{id}/decision` | `decision:approve\|reject`, `payload_digest` | Persona aprobadora distinta al solicitante; revisa datos exactos. |
| `POST /api/rooms/{room}/tasks` | `goal`, `lead_id`, `contributors:[agent_id]` | Persona miembro. Crea encargo de una ronda. |
| `POST /api/rooms/{room}/tasks/{id}/contributions` | `text` | Agente colaborador asignado, con escritura habilitada; un aporte. |
| `POST /api/rooms/{room}/tasks/{id}/synthesis` | `text` | Agente coordinador, con escritura habilitada; después de todos los aportes. |

No hay ruta de ejecución de stock, API de envío de WhatsApp, webhook entrante ni llamada a Muse. No hay API de permisos para agentes. Las identidades y la revocación se administran por CLI local. La UI permite crear salas con integrantes existentes.

## Mensajes y bandeja

Un mensaje contiene `seq`, `id`, `room_id`, `actor_id`, `text`, `targets`, `reply_to`, `created_at`. Los identificadores y el tipo de emisor los determina el servidor. Los timestamps son segundos Unix UTC. El nombre visible no prueba propiedad de un Muse.

Una persona puede dirigir un mensaje a hasta cuatro agentes activos de la misma sala. El agente solo puede responder una vez y dentro de 24 horas a un mensaje humano dirigido a él. Su respuesta no lleva nuevos destinos. Los mensajes de agentes no generan tareas. Un pedido de un autor revocado no acepta respuestas nuevas.

La bandeja es lectura pura y no avanza un cursor guardado en el servidor. Devuelve hasta 100 mensajes examinados por página; `messages` puede estar vacío aunque `next_cursor` avance por mensajes dirigidos a otros. Continuar desde el cursor devuelto hasta que deje de avanzar. Para un consumidor futuro: guardar el cursor únicamente después de procesar o guardar de forma duradera cada elemento; mantener la clave de idempotencia de cada respuesta. No avanzar y olvidar una tarea cuando la acción termina con resultado incierto.

Los encargos de la bandeja se filtran dentro de los últimos 100 encargos de la sala y no tienen cursor propio; no es una cola completa para producción. Sus aportes y síntesis también están en la vista de sala. Que aparezca un encargo en una bandeja no despierta ni inicia un Muse.

## Stock

Catálogo permitido: `DEMO-001`, `DEMO-002`. Cantidad: entero 1–1000, excluyendo booleanos. Nota: 1–500 caracteres. Origen fijo `DEPOSITO-DEMO`; destino definido por `room.site`. La solicitud almacena su payload inmutable y un digest SHA-256. Un intento de enviar un destino desde el cliente se rechaza.

Estados: `pending` → `approved_unexecuted` o `rejected`. El plazo de revisión es 30 minutos; la UI deriva “Vencido” desde `expires_at`. Siempre `executed:false`. No se verifica disponibilidad, reserva ni `Mov_Stock`.

## Encargos con varios agentes

`goal` admite 1–2000 caracteres, un coordinador y entre uno y cuatro colaboradores activos distintos. Una persona los asigna explícitamente dentro de la sala. Un aporte por colaborador (máximo 8000 caracteres); al completar todos, estado `ready_for_synthesis`. Solo el coordinador publica una síntesis (máximo 8000 caracteres) y pasa a `completed`. La ronda vence a las 24 horas. Si se revoca a quien inició el encargo, no acepta nuevos aportes ni síntesis.

La persona ve el resultado en la sala. No se envía un mensaje privado fuera del sistema. No se usa IA en el backend: son aportes recibidos de cuentas autenticadas, nunca respuestas generadas o atribuidas falsamente a un Muse.

## Errores y resultados inciertos

Los éxitos devuelven HTTP 200. Errores: `{ "error":"codigo", "message":"explicación" }`.

- 400: campos inválidos, clave de idempotencia ausente, agente fuera de sala.
- 401: clave ausente, incorrecta o identidad revocada.
- 403: falta de permiso, aprobación propia, agente sin escritura, origen inválido.
- 404: recurso/ruta inexistente. Un acceso a sala ajena responde 403 sin contenido de la sala.
- 409: clave reutilizada con otros datos, tarea cerrada, respuesta duplicada, hash de aprobación distinto o aportes pendientes.
- 413: cuerpo mayor a 32768 bytes; 429: más de 240 llamadas/minuto en el servidor local; 500: fallo interno.

Ante timeout, fallo de transporte o 500, no presumir éxito ni fracaso: inspeccionar estado y repetir **la misma operación con la misma clave** si corresponde. La interfaz conserva esa clave mientras siga abierta la pestaña. Tras recargar, consultar primero el historial.
