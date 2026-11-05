# GL Sala

**Prototipo local para que Parker, el personal y cuentas de agentes compartan pedidos y resultados.** Código publicado en la carpeta `gl-sala/` de [parkerleegl/GH](https://github.com/parkerleegl/GH/tree/main/gl-sala). La aplicación no está desplegada ni conectada a Muse, WhatsApp o stock.

La primera experiencia es **varias personas + una cuenta reservada para Muse_HQ (GL)**. Las personas dejan mensajes dirigidos a GL; Parker puede ver los pedidos y las respuestas registradas. También hay una modalidad de varios agentes: una persona inicia un encargo, los colaboradores aportan y la cuenta coordinadora entrega la síntesis en la sala.

> Crear una cuenta llamada Muse_HQ no conecta tu Muse personal. Las respuestas de las pruebas son simuladas. No existe aquí una API que invoque a GL, un trabajador que lo active ni acceso a su memoria o sus conversaciones privadas.

## Qué funciona hoy

- Interfaz en español, salas persistentes en SQLite y actualización cada cinco segundos.
- Identidades separadas para personas y agentes. Claves individuales aleatorias; la base guarda sus hashes. Acceso limitado por sala y revocación inmediata para nuevas llamadas.
- Pedidos dirigidos explícitamente a agentes, bandeja de lectura y respuestas vinculadas. Una respuesta por agente/pedido, con vencimiento de 24 horas. Ningún mensaje de agente inicia otro automáticamente.
- Rondas de colaboración: hasta cuatro colaboradores, un coordinador distinto y una síntesis después de recibir todos los aportes. Sin rondas automáticas adicionales.
- Solicitudes de stock con catálogo ficticio, destino fijado por la sala y aprobación por otra persona con ese rol. La aprobación vence si no se resuelve en 30 minutos. **No hay ejecución de stock.**
- Claves de idempotencia, transacciones y registro de auditoría encadenado. Una aprobación queda ligada al contenido exacto que se revisó.
- 29 pruebas automatizadas de dominio y HTTP; revisión funcional en navegador. Detalles en [VALIDATION.md](docs/VALIDATION.md).

## Probar en tu equipo

Python 3.9 o superior, sin dependencias externas. Para desarrollo nuevo se recomienda una versión mantenida de Python. No hace falta instalar paquetes ni ingresar claves de Meta.

```sh
cd gl-sala
python3 -m muse_room init-demo
python3 -m muse_room serve
```

Abrir **http://127.0.0.1:8765**. La demo crea claves de prueba en `.local/demo-access.txt`; usar la de `Parker · demo` para entrar. Las cuentas de personal tienen claves distintas. Probar varias personas en pestañas distintas: cada pestaña conserva su clave solo en memoria. Al recargar hay que volver a entrar.

Si la demo ya está inicializada, ejecutar solo `serve`. `init-demo` se niega a sobrescribir una base existente. El proyecto entregado localmente puede tener una demo ya inicializada; el ZIP excluye esa base y todas las claves.

En macOS configurado para escribir caché Python fuera del proyecto, usar `PYTHONDONTWRITEBYTECODE=1` antes del comando si el entorno restringido lo requiere.

La demo incluye:

| Cuenta | Acceso de ejemplo |
| --- | --- |
| Parker · demo | Administración local; revisión de stock en Show |
| Personal Show · demo | Mensajes y solicitudes para Show |
| Supervisor · demo | Mensajes y revisión de stock en Show |
| Muse_HQ · cuenta pendiente | Cuenta de agente de solo lectura; no conectada |
| Agente colaborador · reserva | Cuenta adicional de solo lectura; no representa otro Muse existente |

Las salas iniciales son `Show · Equipo` y `Laboratorio · Agentes`. Elegir Show para el caso principal. Todas las identidades, permisos, locales y productos de la demo son ejemplos; no reflejan permisos reales del negocio.

### Recorrido corto

1. Entrar como Personal Show, escribir un pedido y marcar `Muse_HQ` en “Dirigir a”. El pedido queda registrado; no se envía a Meta.
2. Entrar como Parker en otra pestaña: el pedido y su autor son visibles.
3. Como Personal, usar “Solicitar stock” con un artículo de ejemplo.
4. Como Parker, revisar los datos y aprobar: queda **Aprobado · sin ejecutar**. La misma persona no puede aprobar su solicitud.
5. En Laboratorio, crear un encargo entre agentes. Quedará pendiente hasta que se registren aportes autenticados mediante la API. No aparecerán respuestas inventadas.

## API y conexión con Muse

Meta documenta que Muse puede construir conectores para servicios con API o CLI. Esa es una **vía oficial para experimentar con un conector saliente**: Muse consulta esta sala. No demuestra que podamos llamar al Muse personal desde fuera, despertarlo ni garantizar una respuesta automática. [Fuente oficial](https://research.meta.ai/blog/security-and-safety-for-ai-agents-our-approach-with-muse).

La API de la sala sí está implementada y probada localmente. [Contrato y permisos](docs/API.md), [guía de conector pendiente](docs/MUSE-CONNECTOR.md) y [viabilidad con fuentes](docs/FEASIBILITY.md).

El servidor escucha exclusivamente en `127.0.0.1`: la VM de Muse y otros dispositivos no pueden alcanzarlo. Para una prueba real faltan un servicio HTTPS adecuado, autenticación de personas, configuración y autorización del conector en Muse y pruebas de extremo a extremo. No abrir este servidor a Internet ni añadir un túnel para simular una integración terminada.

## Administración de la demo

La administración por CLI confía en la persona que tiene acceso al archivo de base de datos. La interfaz permite crear salas con identidades existentes; no cambia los permisos de los sistemas reales.

```sh
# Persona nueva de prueba (luego elegirla al crear una sala).
python3 -m muse_room add-identity --name 'Otra persona de prueba'

# Cuenta de agente nueva: por defecto solo lectura.
python3 -m muse_room add-identity --name 'Otro agente pendiente' --kind agent

# Solo para un ensayo local de respuestas autenticadas; NO conecta un Muse.
python3 -m muse_room add-identity --name 'Agente de ensayo' --kind agent --agent-write

# ID devuelto en el archivo de acceso. No usar el nombre visible.
python3 -m muse_room revoke ID_DE_LA_IDENTIDAD
python3 -m muse_room verify-audit
```

Cada alta guarda la clave una sola vez en un archivo privado de `.local/`. Las claves de agente nunca deben recibir el rol ni la clave de una persona. Para un ensayo sin datos anteriores se puede usar otro directorio: `python3 -m muse_room --data .local/otra-demo init-demo`.

## Verificación y GitHub

```sh
python3 -m unittest discover -s tests -v
node --check web/app.js   # opcional, si Node está instalado
```

Las pruebas HTTP requieren permiso para abrir un puerto de loopback. No consultan Internet ni llaman a Meta. La configuración de GitHub Actions está incluida como plantilla en `gl-sala/.github/workflows/test.yml`. Al estar dentro de la subcarpeta, GitHub no la ejecuta automáticamente. No se agregó ningún workflow a la raíz del repositorio.

Este código se publica en el repositorio público `parkerleegl/GH`, exclusivamente dentro de `gl-sala/`, conservando su README y demás archivos existentes. No se añadió una licencia; revisá [SECURITY.md](SECURITY.md) antes de usarlo con datos reales. `.gitignore` excluye claves, SQLite, entornos y cachés. El ZIP de entrega contiene únicamente código, documentación y pruebas. No subir `.local/`, cookies de Muse ni sesiones de WhatsApp.

## Límites concretos

Es una base funcional de colaboración local, no un sistema de producción. No hay acceso remoto entre dispositivos, inicio de sesión empresarial, recuperación o rotación de claves, verificación de titularidad de un Muse, notificaciones, cancelación de encargos, edición de miembros de salas existentes ni integración con inventario. La revocación actual deshabilita una identidad completa.

Las vistas muestran los últimos 100 mensajes, solicitudes y encargos. Mensajes y auditoría tienen paginación API; la lista de encargos y stock está acotada a 100. No usarla como cola de producción de alto volumen. Las decisiones de stock no reservan mercadería ni prueban disponibilidad. La trazabilidad local no sustituye `Mov_Stock` ni recibos de un ERP.

El código no proporciona una licencia de terceros ni autorización de marca. `GL Sala` es el nombre del prototipo; no está afiliado con Meta.
