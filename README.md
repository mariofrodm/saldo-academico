# Saldo · Finanzas personales con IA

Saldo registra ingresos, gastos, abonos, recurrentes y metas de ahorro en GTQ.
Sus tres asistentes consultan registros propios y fuentes educativas; los agentes
de presupuesto y metas también pueden combinar datos externos y cálculos. Los
pagos son registros manuales: no hay conexión bancaria ni transferencias reales.

Para entender el proyecto sin conocer su código, leer primero
[Cómo funciona Saldo, de principio a fin](docs/como-funciona.md). Incluye recorrido
de los datos, arquitectura, tecnologías, agentes, RAG, memoria, cuotas, publicación
y Power BI. El [estado verificable](docs/estado.md) distingue la implementación,
los ensayos locales, la versión publicada y los archivos de entrega.

[Aplicación HTTPS](https://saldo-academico.onrender.com) ·
[API / Swagger](https://saldo-academico.onrender.com/docs) ·
[GitHub Actions](https://github.com/mariofrodm/saldo-academico/actions).

## Puesta en marcha local

Se necesitan Git y Docker con Compose. En Ubuntu no hace falta instalar Python,
Node o PostgreSQL globalmente para ejecutar los contenedores.

1. Clonar el repositorio y copiar `.env.example` a `.env`.
2. Reemplazar los valores `CAMBIAR` por cuatro contraseñas propias e
   independientes. Las cuentas iniciales exigen al menos 16 caracteres. Mantener
   coherentes `POSTGRES_PASSWORD` y la contraseña de `DATABASE_URL`.
3. Mantener `APP_ENV=local`, `COOKIE_SECURE=false` y la conexión al servicio `db`.
4. Ejecutar:

```sh
docker compose -p saldo_academico up --build -d --wait
docker compose -p saldo_academico exec app python -m backend.seed
docker compose -p saldo_academico exec app python -m backend.demo
docker compose -p saldo_academico exec app python -m backend.knowledge
```

Abrir [la aplicación local](http://localhost:8000) y
[Swagger local](http://localhost:8000/docs). El arranque aplica las migraciones.
El seed crea cuentas, servicios y datos básicos; `demo` amplía explícitamente
el escenario local de Ana; `knowledge` indexa las guías educativas Markdown.
Las importaciones son idempotentes y no equivalen a publicar código. Esta receta
crea datos solo en la base local: no sincroniza automáticamente la cuenta Ana
con Neon. El despliegue actualiza código y esquema; copiar registros financieros
entre instalaciones es una operación independiente y controlada.

Las cuentas iniciales son `admin@example.test`, `demo@example.test` y
`bi@example.test`. Sus contraseñas son las elegidas en `.env`, que no deben
publicarse. El seed no muestra ni reemplaza contraseñas de cuentas existentes.
La cuenta nueva registrada desde el login empieza sin datos financieros.

Sin `GROQ_API_KEY` se pueden probar identidad, datos, reportes y respuestas
calculadas admitidas. La inferencia real necesita una clave Groq Free y cuota
disponible. No se requiere entrenar el modelo.

Para apagar conservando registros, usar `docker compose -p saldo_academico down`
sin `--volumes`. La receta local no debe apuntarse a Neon para ejecutar pruebas.
Ver [instalación y recuperación](docs/portabilidad.md).

## Pruebas y demostración

```sh
docker compose -p saldo_academico exec app pytest -q
```

La suite backend crea una base temporal local independiente y simula Groq y las
fuentes externas: no consume tokens. El Dockerfile también ejecuta pruebas de
frontend y compila TypeScript/React. Desde `frontend/`, con Node 24 y `npm ci`,
se puede ejecutar `npm test` y `npm run build` por separado.

- [Guion corto de exposición](docs/guion-demostracion.md).
- [Aceptación completa paso a paso](docs/aceptacion-final.md).
- [Escenario de referencia y cifras históricas](docs/escenario-demo.md).
- [Auditoría conversacional y límites](docs/auditoria-conversacional.md).

`scripts/verificar_aceptacion.py` comprueba la API local sin usar Groq. Los
resultados fechados y el estado de CI/cloud se consultan en `docs/estado.md`;
un número anterior de pruebas no acredita una publicación posterior.

La implementación final acreditada pasó **417 pruebas backend y 106
subpruebas**, **14 frontend**, **63 comprobaciones locales**, **65 cloud de
lectura** y **31 de congelación**. La [matriz del enunciado](docs/cumplimiento.md)
registra 15 criterios comprobados con sus límites y evidencia; no certifica toda
respuesta posible del modelo.

## Cuentas, administración y datos

El acceso permite **Crear cuenta** con correo y contraseña de 12 a 128
caracteres; `name` es opcional. El servidor asigna rol `user` y cuota inicial de
20.000 tokens. El registro devuelve una sesión igual que el login y rechaza
correos duplicados y campos para escalar permisos.

Administración permite crear, listar, editar y dar de baja usuarios. El rol se
elige al crear; no se cambia mediante la edición común. La baja de usuario es
lógica: revoca sesiones y conserva finanzas e historial. Se puede reactivar;
no se permite la propia baja ni dejar sin administrador activo.

Las configuraciones IA ocupan los tres espacios implementados (`rag`, `budget`
y `goals`). El administrador las crea/recrea, consulta, edita y da de baja de
forma lógica, preservando historial y consumo. Dar un nombre nuevo a una
configuración no implementa una herramienta o agente nuevo.

Los importes y cálculos usan `Decimal`/`NUMERIC`. Los abonos se registran
separados de los compromisos; no se puede abonar más del pendiente. Las metas
muestran movimientos en acordeones independientes. Su eliminación confirmada
borra también sus movimientos y cambia los totales históricos de ahorro; la
acción conserva auditoría. Las plantillas recurrentes normalizan el inicio al
primer día del mes y sus ediciones no reescriben instancias anteriores.

## Asistentes y API

Los tres asistentes usan instrucciones versionadas, un corpus recuperable por
búsqueda textual de PostgreSQL y herramientas de lectura con usuario fijado en
el servidor. El recorrido general carga la guía `00`; dos recorridos externos
acotados usan instrucciones específicas compactas de `external_system` y
herramientas compuestas para resolver lectura/cálculos/fuente externa en dos
inferencias cuando la petición está completa. No hay embeddings, servicio vectorial ni SQL libre del modelo.
Los cálculos se realizan en el backend. Las fuentes externas disponibles son
inflación anual de Guatemala en Banco Mundial y referencia USD/GTQ en Banguat.
Ver [catálogo y contratos](docs/agentes/README.md).

El servidor reconstruye hasta seis intercambios completos, con referencias
verificadas y contexto acotado. Un mes explícito nuevo tiene prioridad sobre el
anterior. Las conversaciones se separan por asistente; recargar inicia una
vista nueva y el historial persistido permanece disponible.

Las comparaciones sencillas y algunas consultas de margen/metas usan respuestas
calculadas con cero llamadas. Las preguntas abiertas utilizan Groq. Las fuentes,
herramientas y consumo se revisan en Historial. `local_only: true` en la
petición IA permite intentar una respuesta calculada durante una espera o sin
proveedor: si la pregunta requiere inferencia, se informa sin gastar Groq.
No se aumentan cuotas ni se reinician contadores por usar ese modo.

Para probar cálculos propios directamente:

- `GET /api/v1/advisor/tools`: manifiesto autenticado.
- `POST /api/v1/advisor/{tool_name}`: `{"arguments": {...}}` según el manifiesto.

Esas lecturas no llaman a Groq. El contenido educativo no proporciona tasas,
cuotas contractuales ni saldos bancarios que no estén registrados. Una pregunta
documentada no se considera validada en cualquier formulación posible.

## Reporterías y archivos

La web y Power BI usan la misma API de solicitudes y tokens. Power BI importa
desde la URL pública en Render con la cuenta BI de solo lectura; no consulta
localhost ni accede directamente a Neon. `powerbi/consumo.pq` recorre todas las
páginas bajo un mismo corte `as_of`. Los filtros iniciales cubren noviembre de
2026 y se modifican en `FechaDesde`/`FechaHasta`.

Para incorporar nuevas consultas hay que **actualizar el modelo semántico**,
esperar que termine y refrescar la vista. Un PBIX descargado y un PDF existente
no se actualizan automáticamente; sus cortes se documentan en `estado.md`. El
cierre del 8/11 compara 9 solicitudes, 22 llamadas y 17.495 tokens; el PDF final
tiene 12 páginas y el PBIX incluye informe y modelo verificados desde Ubuntu.

- [Informe técnico y evidencias PDF](output/pdf/Informe_Saldo_Academico.pdf).
- [Power BI con informe y modelo PBIX](powerbi/Saldo_Consultas_y_Consumo.pbix).
- [Colección Postman](docs/postman.json), sin contraseñas ni tokens guardados.
- [Alcance aprobado](docs/alcance.md), [arquitectura](docs/arquitectura.md) y
  [matriz de cumplimiento](docs/cumplimiento.md).

El trabajo se realiza desde Ubuntu. Power BI Desktop requiere Windows; usarlo
para abrir el PBIX es una comprobación separada que solo se afirma si se ejecutó.
No requiere trasladar los servicios cloud.

## Operación gratuita y secretos

Render, Neon y Groq usan Free con cuotas y pausas por inactividad. La licencia
institucional de Microsoft debe revisarse antes de presentar. Aumentar una cuota
local no compra créditos ni amplía el límite real de Groq. No añadir tarjetas,
planes de pago, cron pagado ni pings para impedir las suspensiones.

No versionar `.env`, `.env.cloud`, claves, sesiones, credenciales BI, hooks ni
respaldos privados. Las credenciales locales y cloud son independientes.
Ver [operación y cuotas](docs/operacion.md).
