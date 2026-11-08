# Matriz de aceptación del enunciado

Se desglosó el enunciado original en **15 criterios verificables**. Cada fila se
marca por su evidencia, sin asignar pesos ni inventar un porcentaje de nota.
`Comprobado` corresponde a los casos y entornos indicados; no garantiza cualquier
formulación del modelo ni disponibilidad permanente de una capa gratuita.

| ID | Requisito | Estado | Evidencia y alcance |
|---|---|---|---|
| A01 | Objetivo, usuarios, fuentes y tres servicios; arquitectura GUI/API/BI | Comprobado | Alcance aprobado, arquitectura y guía completa del recorrido; diagramas y modelo relacional en PDF. |
| A02 | Login/logout, roles e aislamiento | Comprobado | Suite de permisos y sesiones; aceptación cloud de lectura; usuario, admin y BI con ámbitos separados. |
| A03 | CRUD de usuarios, dominio, corpus y configuraciones IA | Comprobado | API/GUI y pruebas; bajas lógicas de usuario y configuraciones; meta y movimientos eliminados solo con confirmación. Tres espacios especializados de servicio. |
| A04 | RAG de BD con fuentes, memoria e insuficiencia | Comprobado | Recuperación textual PostgreSQL y guías; conversación acotada; RAG real cloud con una llamada, 2.256 tokens, más regresiones de seguimiento y ausencia de datos. |
| A05 | Agente de presupuesto con fuente externa y varios pasos | Comprobado con alcance | Herramienta compuesta elegida por el modelo: lectura propia más Banco Mundial, dos inferencias, 1.731 tokens. Aritmética contrastada; la recomendación de capacidad detectada se cubrió con guarda y repetición offline del candidato real. No certifica toda recomendación posible. |
| A06 | Agente de metas con fuente externa y escenarios | Comprobado con alcance | Cloud: dos llamadas, 2.186 tokens, lectura y Banguat/cálculos correctos; se detectó una afirmación de plazo. Con instrucciones corregidas, ensayo local real: dos llamadas, 2.693 tokens, proyecciones correctas sin prometer el calendario contractual. |
| A07 | Historial propio y vista/filtros globales del admin | Comprobado | Preguntas, errores, herramientas y rondas persistidos; lectura autenticada y aislamiento. |
| A08 | Cuotas, bloqueo y contabilidad de todas las rondas | Comprobado | Reservas atómicas, límites personal/día/minuto, recuperación, errores y 0 tokens en rutas calculadas; no se reiniciaron cuotas. |
| A09 | API REST autenticada, Swagger y consumo externo | Comprobado | Cliente HTTP externo, login, servicios, historial, advisor y reportes; colección Postman actualizada sin credenciales. |
| A10 | Reporte web de solicitudes y tokens con filtros | Comprobado | Contraste cloud y filtros en navegador; distinción de preguntas/llamadas, fechas Guatemala y ámbito usuario. |
| A11 | Power BI consume API, coincide y se entrega archivo completo | Comprobado | Refresh 8/11 04:58:22 Guatemala; 9 solicitudes, 22 llamadas y 17.495 tokens; filtros fecha/servicio/vacío; PBIX descargado e inspeccionado desde Ubuntu, modelo y nueve IDs coincidentes. |
| A12 | Pruebas automatizadas de IA, historial y consumo | Comprobado | 417 pruebas backend y 106 subpruebas, 14 frontend, 63 comprobaciones locales, 65 cloud de lectura y 31 de congelación; proveedor simulado en suites. |
| A13 | Aplicación/API cloud y persistencia | Comprobado | Render/Neon Free, HTTPS, migraciones y health del commit publicado; configuración privada y respaldo/restauración separados. |
| A14 | CI/CD despliega solo tras pruebas exitosas | Comprobado | CI 42499168192: backend, container y deploy exitosos; health bb4dc3293d90307dc6afce6be729e022b40fb0f8, base ok. Auto-deploy directo apagado. |
| A15 | Repositorio, SQL/datos, PDF, enlaces y demostración | Comprobado | Clon limpio, SQL/migraciones/seed, restauración privada, Postman y enlaces; PDF final de 12 páginas renderizado/inspeccionado y PBIX completo contrastado; ambos sin secretos conocidos. Guion documentado. |

Al corte de entrega hay **15 de 15 criterios comprobados dentro del alcance
y casos descritos** (100 % de esta lista de aceptación, no una estimación de
nota ni una promesa de respuestas infalibles). Las filas A05/A06 describen explícitamente las
limitaciones detectadas y cómo se comprobaron las barreras, sin convertir un
HTTP 200 en certificación de calidad.

La copia del escenario financiero ampliado de Ana a Neon es una operación
adicional pendiente de confirmación específica. La semilla cloud básica permite
verificar los requisitos originales; no se presenta como si contuviera los datos
locales ampliados. Esa copia pendiente no se oculta dentro de una declaración de
«todo sincronizado». El corte exacto de publicación y archivos está en
[estado](estado.md).
