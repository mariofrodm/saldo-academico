# Estado verificable - 8 de noviembre de 2026

Este archivo distingue código, pruebas locales, publicación y archivos. La
presencia de una función o de un PBIX antiguo no acredita el cierre de una
versión nueva. El cierre de esta revisión está en ejecución; las cifras finales
se incorporan cuando existan sus evidencias, sin extrapolar resultados.

## Implementación disponible

- React/TypeScript/Vite y FastAPI/Python, servidos desde un origen; PostgreSQL,
  Docker, migraciones Alembic y documentación Swagger.
- Registro público, login/logout, sesiones y CSRF, roles admin/user/BI,
  aislamiento de finanzas, historial y herramientas por usuario.
- Usuarios, categorías, obligaciones, pagos parciales, arrastre sin duplicados,
  recurrentes mensuales, metas, aportes/retiros y auditoría.
- Interfaz con formularios de creación arriba, montos alineados, acciones con
  iconos y etiquetas en español, estados de color y acordeones independientes.
- Eliminación confirmada de una meta y sus movimientos, transaccional y auditada.
- Chat con tres servicios, RAG textual sobre PostgreSQL, documentación educativa
  versionada, herramientas financieras de lectura, agentes con Banco Mundial
  y Banguat, memoria acotada y respuestas naturales.
- Cuotas personales y compartidas, reserva antes de inferencia, conciliación de
  todas las rondas, historial de herramientas y reportes con paginación/corte.
- Flujos de respuesta calculada sin proveedor y compactación de contexto.

Los ajustes de cierre incluyen CRUD completo de las configuraciones de los
espacios `rag`/`budget`/`goals`, persistencia del inicio de recurrentes y modo
`local_only` para consultas calculadas durante esperas. La suite final y su
publicación deben acreditar la revisión que contiene estos ajustes.

## Pruebas locales anteriores al último cierre

La última suite completa registrada antes de los ajustes de cierre pasó **307
pruebas backend y 106 subpruebas**, más **13 pruebas frontend** y **61
comprobaciones de aceptación**, sin consumo de Groq en esa aceptación.
La evidencia está en `evidencias-locales/auditoria-conversacional/` y se conserva
fuera del repositorio por privacidad. No atribuir estas cifras a un CI o SHA
posterior hasta volver a ejecutar sus verificaciones.

## Publicación y Power BI: corte histórico acreditado

- Publicación previa en `https://saldo-academico.onrender.com`, base Neon Free,
  PostgreSQL 18.6 y conexiones TLS. Las pruebas locales usan PostgreSQL 17.
- CI/CD histórico exitoso:
  [ejecución 41423307877](https://github.com/mariofrodm/saldo-academico/actions/runs/41423307877),
  commit `0c5d2f7b0df16b643fc070056fd57563e0b2bedf`, del 2 de noviembre.
- Power BI importa la API HTTPS con Basic de lectura, sin gateway local, con
  paginación y un corte estable por actualización.
- El refresco manual del modelo fue comprobado el **8/11 a las 03:56 Guatemala**
  sobre esa publicación previa: **5 solicitudes, 15 llamadas, 9.716 tokens**.
  Esa actualización no acredita la nueva versión ni importa datos de localhost.
- La programación de actualización estaba desactivada. Power BI/Fabric mostraba
  **11 días de prueba** en esa inspección; revisar vigencia antes de la entrega.
- El PBIX y PDF guardados al inicio de esta revisión eran del 2 de noviembre.
  Deben regenerarse o descargarse después del contraste definitivo.

## Cierre pendiente de acreditar para la revisión nueva

1. Suite final, compilación y aceptación de los ajustes recientes.
2. SQL final y migraciones sincronizados; arranque desde un clon limpio y
   restauración en una base nueva, sin alterar la original.
3. Commit de implementación, CI/CD exitoso y `/api/health` público con ese SHA.
4. Preparación controlada de corpus/datos cloud y aceptación de los tres
   servicios, incluida fuente externa y cálculos en cada agente especializado.
5. Consumo externo autenticado desde cliente, historial y reportes cloud.
6. Web/API/Power BI coincidentes en fechas, servicio, alcance y conjunto de
   solicitudes; actualización completada y PBIX completo descargado.
7. PDF con datos, capturas, modelo, SHA, pruebas y enlaces actuales; escaneo de
   secretos en repositorio y exportaciones.

## Condiciones de operación

Costo permitido USD 0. Render, Neon y Groq Free tienen cuotas y pausas por
inactividad; abrir la aplicación antes de la exposición sin pings artificiales.
Una cuota personal mayor no amplía Groq ni el presupuesto compartido. El
contador compartido diario de la app usa UTC: renueva a las 18:00 Guatemala.
La cuota personal es acumulada y no se reinicia con ese día.

La cuenta BI consume reportes; no debe usarse como usuario de IA. Las
credenciales local/cloud son independientes y permanecen fuera de Git. La
clave Groq configurada se creó con vencimiento el 2/12/2026; comprobar su estado
sin exponerla. Retirar accesos temporales al terminar.

Todo el desarrollo y la gestión web se realizan desde Ubuntu. Power BI Desktop
en Windows no se ha ejecutado en esta auditoría; abrir el PBIX allí es una
comprobación separada y no requiere trasladar la aplicación.
