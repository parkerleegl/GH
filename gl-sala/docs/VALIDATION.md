# Validación local · 2026-11-05

## Resultado

**29 pruebas automáticas aprobadas**, Python 3.9.6 en macOS, sin paquetes externos. Comando:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

`node --check web/app.js` aprobado con Node 24.22.0. Compilación de módulos Python aprobada con la caché redirigida a `/tmp` por las restricciones de este entorno.

Las pruebas HTTP abrieron únicamente un puerto aleatorio en `127.0.0.1`, autorizado por el entorno. El primer intento con el sandbox no podía abrir ese puerto; la ejecución local autorizada completó las pruebas. La verificación encontró y corrigió el manejo de query strings vacías en Python 3.9.

## Cobertura significativa

- Autenticación, ausencia de claves en vistas, separación de salas para lectura, mensajes, auditoría y bandeja.
- Creación de salas solo por administradores humanos; rechazo de suplantación y de agentes aprobadores.
- Texto de conversación sin efectos sobre stock, incluso con instrucciones de ignorar permisos.
- Reintentos idempotentes, conflicto de contenido y doce reintentos concurrentes que producen una sola solicitud.
- Agente de solo lectura, destino explícito, una respuesta por agente, rechazo de ciclos agente→agente y vencimientos.
- Validación de SKU/cantidad/destino, separación solicitante/aprobador, digest exacto, caducidad, rechazo y ausencia de ejecución.
- Dos aprobaciones simultáneas: solo una se acepta.
- Revocación bloquea lectura, escritura y replay; pedidos de autores revocados no admiten nuevas respuestas, aportes ni revisión de stock.
- Aportes solo de colaboradores asignados; síntesis solo del coordinador después de todos los aportes; agentes no crean rondas.
- Paginación de mensajes y detección de alteración simple de auditoría.
- HTTP: Host/Origin, acceso autenticado, CSP, bloqueo de rutas privadas, JSON malformado/duplicado/no finito y tamaño de cuerpo.

## Revisión de interfaz

En el navegador local, con una base temporal de datos sintéticos:

- Entrada con la clave de una persona de prueba; visualización del equipo y de la cuenta Muse_HQ pendiente.
- Envío de un pedido dirigido a Muse_HQ y aparición en el historial compartido, sin enviar nada a Meta.
- Revisión y aprobación de una solicitud: resultado visible **Aprobado · sin ejecutar**.
- Cierre de sesión, limpieza de datos de la pantalla y entrada con otra identidad sin salas; no se mostraron datos de la sesión previa.
- Inspección de escritorio y ancho de 390 px; ancho de contenido igual al viewport, sin desborde horizontal. Sin errores ni advertencias de JavaScript en el recorrido observado.

Se corrigió la limpieza visual al cambiar de identidad antes de la entrega. La prueba visual no equivale a una suite automatizada completa de frontend ni a pruebas con personas remotas.

## Fuera de validación

No se probaron Muse personal, un conector real, activación automática, WhatsApp, Meta Model API, cuentas empresariales, stock, ERP, `Mov_Stock`, alojamiento ni despliegue. Durante estas pruebas no se publicaron repositorios ni mensajes externos. La publicación posterior del código en `parkerleegl/GH/gl-sala` no implica un despliegue ni una conexión. La plantilla de GitHub Actions está dentro de la subcarpeta, por lo que no se ejecuta automáticamente; sus versiones adicionales de Python no se probaron localmente.

El servidor de revisión se detuvo al terminar. La demo de `.local/` queda disponible en el proyecto local, pero se excluye por completo del archivo ZIP. El empaquetado usa una lista explícita de carpetas/extensiones de código y documentación; se verificó que el ZIP no contiene claves de la demo ni archivos de runtime.
