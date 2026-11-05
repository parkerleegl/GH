# Viabilidad revisada · 5 de noviembre de 2026

## Resultado

Existe un camino documentado para **Muse → API de la sala**, mediante un conector personalizado. Aún no está validado con el Muse personal de Parker. No se encontró documentación oficial suficiente para afirmar que **la sala → invocación del Muse personal GL** esté disponible. Esta distinción define el alcance del proyecto.

| Necesidad | Evidencia y decisión |
| --- | --- |
| Varias personas asignan trabajos a GL y Parker observa | Sala propia con miembros y API implementada. La recepción y respuesta de GL requieren configurar y probar un conector saliente. |
| GL entra al grupo WhatsApp existente | No verificado. Queda fuera de esta versión. |
| Varios Muse colaboran | Identidades, encargos y síntesis implementados; cada Muse real necesita un conector y permisos propios. El backend no activa ninguno. |
| Un modelo de Meta contesta por API | La API de modelos permite construir un agente nuevo. No concede acceso al Muse personal de Parker ni a sus conectores. No se implementó esa sustitución. |
| Stock con permisos | Solicitud y revisión locales implementadas. No hay ejecutor, conexión a inventario ni cambios reales. |

## Fuentes oficiales y alcance

1. [Meta AI Research — How We Built Safety Into Muse](https://research.meta.ai/blog/security-and-safety-for-ai-agents-our-approach-with-muse), secciones Connectors y Human in the Loop. Meta describe conectores personalizados para servicios con API o CLI, una VM propia y controles de aprobación. **Inferencia de diseño:** una API de sala puede ser candidata a un conector saliente. El artículo no valida este proyecto ni garantiza una entrada remota para tareas, eventos o mensajes de terceros.
2. [Ayuda Meta — Cómo funciona Muse con los conectores](https://www.meta.com/es-es/help/superintelligence/1687253048996149/). Describe pedir a Muse que cree un conector personalizado y gestionar su acceso. No demuestra que un grupo pueda invocar al Muse personal ni que éste deba actuar con permisos del propietario ante cualquier pedido de otra persona.
3. [Muse Connector Platform — Connector guidelines](https://platform.muse.ai/docs). Describe documentación de API/MCP, autenticación, permisos de lectura/escritura y revisión de conectores. No hay aprobación ni registro de este proyecto en esa plataforma. La clasificación de herramientas incluida aquí es una propuesta para el ensayo, no una autorización de Meta.
4. [Meta Model API — Overview](https://developer.meta.ai/docs/overview). Presenta una API de inferencia y Muse Code. No equivale a acceder a una instancia personal de Muse. Usarla sería crear otro agente con su propia memoria, herramientas y credenciales.
5. [WhatsApp Groups API](https://developers.facebook.com/documentation/business-messaging/whatsapp/groups.md/) y [Get started](https://developers.facebook.com/documentation/business-messaging/whatsapp/groups/get-started.md/). La documentación consultada especifica cuenta empresarial oficial (OBA), número en Cloud API y grupos por invitación; indica hasta ocho participantes. No se verificó elegibilidad de Parker ni migración del grupo existente. Esta API no añade por sí sola el Muse personal. Algunas páginas de referencia devolvieron 429 o no fueron accesibles; no se implementaron esquemas basados en suposiciones.

La anterior mención conversacional de una nota periodística no se usa como prueba de integración. No se concluye que una función sea imposible solo porque no apareció en la búsqueda; se marca **no verificada**.

## Por qué una sala propia primero

El backend ya puede recibir mensajes de personas autenticadas, limitar su alcance a una sala, ofrecerlos a un agente autorizado y registrar su respuesta. Para GL habría una dirección inicial: **GL consulta el servicio**. Que GL revise la bandeja periódicamente, reciba un aviso o continúe en segundo plano son pruebas separadas, todavía pendientes. En esta versión se puede inspeccionar el trabajo sin depender de esa activación.

No se exportaron cookies, no se usaron endpoints internos de Muse ni automatización de WhatsApp Web. No se conectaron cuentas existentes, no se modificaron permisos reales y no se enviaron mensajes a otras personas.

## Puertas antes de un piloto

- Elegir alojamiento, visibilidad y responsables; sustituir el servidor local por uno adecuado para HTTPS e identidades verificadas.
- Definir qué personas pueden asignar qué trabajos; el texto de una sala es dato no confiable, no una delegación de todos los permisos personales de Parker.
- Configurar un conector de prueba para una cuenta de agente de solo lectura y una sala sintética. Verificar con el Muse real qué recibe, dónde guarda las credenciales y cómo aplica aprobación.
- Probar respuesta, identidad, revocación, duplicados, vencimiento y aislamiento. Mantener la conexión marcada como no verificada hasta completar el recorrido real.
- Si se desea automatización, confirmar un mecanismo oficial de activación y probarlo por separado. No asumir que el conector despierte a Muse.
- Stock real requiere contrato del inventario, identidad de ejecutor independiente, aprobación exacta, idempotencia también en el sistema destino y conciliación ante resultados inciertos. No está incluido.
