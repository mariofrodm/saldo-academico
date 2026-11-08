# Auditoría conversacional del asesor · 08/11/2026

Las respuestas acotadas sobre estados de metas, prioridad con poco margen y
una meta ambigua ya tienen una salida determinista correcta en los casos
probados. Las respuestas abiertas del modelo siguen necesitando revisión:
`gpt-oss-120b` con razonamiento medio mejoró las cifras, pero aún confundió
conceptos y omitió parte del inventario. **No se declara un asesor infalible ni
un ganador definitivo entre 20b y 120b.** La guarda numérica ya está implementada
y contrastada sin nuevas llamadas contra respuestas reales archivadas. Los
recorridos finales de ahorro y quincena ya se ejecutaron: el primero fue correcto
para el escenario probado; el segundo mantiene límites semánticos. La suite
de esa fase aprobó 275 casos backend y 97 subpruebas, además de 13 casos frontend.
Estos son resultados locales, no una nueva publicación en cloud.

## Comparación inicial con la cuenta original

Evidencia privada: `evidencias-locales/auditoria-chat-final-previo.tar`.
Los dos modelos recibieron las mismas dos preguntas de gastos, con salida
máxima 768 y hasta cuatro rondas. Se comprobó que octubre no cambiara al mes
actual al preguntar «En ese mes…».

| Modelo | Ranking de octubre | Seguimiento alimentación/universidad | Tokens de esos dos turnos |
| --- | --- | --- | ---: |
| gpt-oss-20b | Vivienda Q1.500; gasto Q7.177 | Q1.000 frente a Q900, conserva octubre | 4.987 |
| gpt-oss-120b | Vivienda Q1.500; gasto Q7.177 | Q1.000 frente a Q900, conserva octubre | 5.031 |

Ambos acertaron estos casos pequeños. 120b también respondió diferencia Q100
y deuda total Q7.900, con saldos 550/2.050/5.300 y menor saldo 550. Eso no prueba
que sea mejor en todas las preguntas. Hubo bloqueos 429; uno conservó 2.014
tokens consumidos antes de detener una ronda posterior. **Un error HTTP no
implica consumo cero.** Los bloqueos y sus llamadas previas se mantienen.

Después cambió el código de contexto, herramientas y guardas. Las fases que
siguen no forman una comparación controlada final entre ambos modelos.

## Recorrido real de las fixtures aisladas

Cada fixture creó una base temporal y una cuenta sintética con la cuota
predeterminada de 20.000 tokens, sin aumentar/resetear la cuota original de
Ana. El origen se leyó sin escribir; se copiaron conservadoramente sus
contadores compartidos. La organización Free de Groq siguió siendo la misma:
**una base de pruebas no genera créditos ni límites nuevos**.

Los JSON están dentro de los TAR privados indicados. Se identifican por la
hora UTC y el sufijo de la base; no contienen credenciales operativas.

| Fase / evidencia | Modelo | Consumo | Resultado y cambio motivado |
| --- | --- | ---: | --- |
| Previa: `auditoria-fixture-previa.tar`,07:45:30,`3a3283349b6b` | 120b low | 6.925 | Dos respuestas; prioridad incorrecta: llamó mayor a Q741,67 que a Q1.025 e inventó un umbral del 50%. Tercer turno HTTP 502, sin detalle original del proveedor. |
| Intermedia: `auditoria-fixture-intermedia.tar`,07:53:55,`13fd42f1e24c` | 120b low | 15.692 | Cuatro HTTP 200, pero estados y prioridad no aprobados. Recomienda 600+1.025+741,67 sin justificar fondos ante flujo Q73. Aclaración de Q100 y ausencia de APR/mínimo sí correctas. |
| Contexto: `auditoria-fixture-contexto.tar`,07:58:49,`f45e7a2e6052` | 20b low | 3.399 | Repitió la consulta de metas ya precargada; la siguiente ronda terminó HTTP 413 por contexto. No hubo respuesta final. |
| Límites: `auditoria-fixture-limites.tar`,08:01:46,`788958d8c1bd` | 20b low | 6.815 | Listado aún llama exigible a la meta vencida. Prioridad ya correcta por guarda del backend, 0 tokens. Seguimiento Q100 terminó HTTP 413 después de 3.640 tokens. |
| Previa final: `auditoria-fixture-previa-final.tar`,08:05:48,`866bf3073960` | 120b | 0 | Tres metas respondidas correctamente por backend sin inferencia; pregunta quincenal bloqueada por contexto antes de proveedor. |
| Razonamiento bajo: `auditoria-fixture-razonamiento.tar`,08:11:03,`fd1c63c32584` | 120b low | 3.541 | Tres respuestas de metas correctas y deterministas. Quincena HTTP 200 incorrecta: divide Q6.000/2 y Q1.677/2, inventa Q3.000 y Q838,50; omite una deuda y llama casi cumplida a la meta ya completa. |
| Razonamiento medio: `auditoria-fixture-medium.tar`,08:16:03,`dcead606110f` | 120b medium | 3.789 | Tres respuestas de metas correctas y deterministas. La cuarta usa importes respaldados sin dividir quincenas, pero mantiene errores semánticos; resultado parcial. |
| Ahorro final: `auditoria-fixture-final.tar`,08:40:30,`46ba4dc4752b` | 120b medium | 3.005 | Cuatro HTTP 200. Las primeras tres respuestas son deterministas; «Al fondo de emergencia» conserva Q100/mes, consulta el cálculo y responde con una sola llamada. Escenario aritméticamente correcto. |
| Quincena final: `auditoria-fixture-final.tar`,08:41:25,`6916d2aa2199` | 120b medium | 3.858 | Cuatro HTTP 200. Las primeras tres respuestas son deterministas. La cuarta usa una llamada, conserva las cifras y pregunta fechas; aún pide datos consultables e infiere causas sin demostrarlas. |

La suma de las fixtures es **47.024 tokens**. Las salidas deterministas con 0
llamadas se identifican como respuestas del backend, no como razonamiento o
consumo del modelo. El intento técnico previo de serialización ocurrió antes
del envío a IA; no se suma como una respuesta ni como consumo de Groq.

Todos los JSON de estas fixtures registran `dropped=true` y
`original_user_counters_unchanged=true`; las bases temporales fueron retiradas
sin cambiar los contadores personales originales. El HTTP 502 inicial queda
con **causa no confirmada**: la hipótesis de `tool_use_failed` no se convirtió
en un diagnóstico porque no se capturó la respuesta original. No reapareció
un HTTP 400 que permitiera verificarla.

## Qué mejoró y qué no

La fase medium mantuvo salida máxima 768, tres rondas y cuota 20.000. En las
primeras tres preguntas no llamó al proveedor:

1. Seis metas: tres en progreso, una cumplida, una vencida y una inactiva.
2. Prioridad: contrastar el flujo de octubre Q73 con la necesidad de ahorro
   Q2.316,67; replantear el plan sin convertir una meta vencida en deuda exigible.
3. Aporte Q100: preguntar a qué meta se refiere antes de proyectar.

La pregunta abierta «Cobro por quincena y siento que no me alcanza» sí consumió
3.789 tokens. Distinguió octubre cerrado de noviembre parcial y conservó los
importes consultados: 7.250/7.177/73 y 6.000/1.677/625/3.698. **No dividió por dos
para inventar un calendario quincenal.** Sin embargo:

- Llamó «gastos recurrentes» a pagos de alimentación Q1.000 y universidad Q400;
  esos pagos ejecutados no son las plantillas recurrentes.
- Mencionó dos de las tres deudas sin aclarar que mostraba una selección.
- La respuesta no demuestra todavía un calendario real por quincenas: faltan
  las fechas de cobro/pago necesarias para construirlo.

Cambiar a medium mejoró este caso numérico; no valida automáticamente todas
sus relaciones, clasificaciones o recomendaciones. La guarda implementada
busca importes sin respaldo en resultados verificados o datos aportados por
el usuario. Si detecta uno, devuelve una explicación natural en lugar de
presentar la respuesta como válida. El paso privado `response_check` conserva
el candidato rechazado y los importes señalados para poder revisarlos.

El contraste offline `evidencias-locales/auditoria-conversacional/validacion-importes-20261108.json`
aplicó la guarda a las respuestas reales archivadas, con **cero llamadas nuevas**:

| Respuesta revisada | Importes señalados |
| --- | --- |
| Low, `fd1c63c32584`, 3.541 tokens históricos | Q3.000,00; Q838,50; Q2.161,50 |
| Medium, `dcead606110f`, 3.789 tokens históricos | Ninguno |

La lista vacía de medium solo acredita respaldo de las cifras comprobadas;
**no valida las relaciones semánticas, clasificaciones o recomendaciones**.
Por eso siguen documentadas la confusión pagos/recurrentes y la selección
incompleta de deudas.

También se limita la repetición del último intento HTTP 429: solo se recuperan
nombres y argumentos de consultas de lectura, para la misma pregunta, dentro
de 15 minutos y del mismo día. Los datos se vuelven a consultar; no se reutiliza
una cifra financiera antigua como si fuera actual. `simulate_goal` queda fuera
de esa repetición para no reutilizar sus importes antiguos. Diez pruebas
dirigidas aprobaron estas restricciones y están incluidas en la suite final.

El contexto de respuesta y el reconocimiento de intención de ahorro preparan
`savings_plan` antes de inferir en el seguimiento «100 al mes → elijo Fondo».
La fixture final `46ba4dc4752b` lo confirmó con una sola llamada y 3.005 tokens:
saldo inicial Q550 + seis aportes de Q100 = Q1.150; faltan Q3.850 para la meta
de Q5.000 y Q641,67 adicionales al mes para cumplir el plazo de seis meses.
La respuesta conserva meta y aporte propuesto, es natural y no afirma que
ese aporte sea asequible. Es un escenario calculado, no un pago ni una promesa.

La fixture final quincenal `6916d2aa2199` consumió 3.858 tokens en una llamada.
No inventó importes quincenales: mantuvo noviembre parcial Q6.000/Q1.677/Q625/
Q3.698 y el margen de octubre Q73; pidió las fechas de cobro. El resultado
semántico sigue siendo **parcial**: pide los montos de gastos fijos que la
aplicación permite consultar, e infiere que gastos fijos y pendientes explican
el problema sin demostrar esa relación. La guarda de cifras no prueba causas.

Ambas fixtures finales terminaron con cuatro HTTP 200, cuota inicial de 20.000,
`dropped=true` y contadores originales intactos. El éxito de estos recorridos
concretos no garantiza todas las formulaciones ni elimina los fallos previos.

Qwen figura como opción del harness y se vio disponible en el listado del
proveedor, pero no se ejecutó una inferencia ni se terminó su integración de
tokenización. No se ofrece como modelo operativo probado. Llama 3.3 no apareció
en el listado consultado. No se inventa una comparación con esos modelos.

## Cuotas y reproducción breve

| Concepto al corte | Tokens |
| --- | ---: |
| Fixtures acumuladas | 47.024 |
| Contador diario original antes de conciliación | 36.980 |
| Contador diario original después de conciliación | **84.004** |
| Margen diario local restante al corte | 15.996 |
| Ana: usados/límite | 54.463/60.000 |
| Ana: reservas / restantes | 0 / 5.537 |

No se realizaron llamadas reales adicionales desde Ana una vez que su margen
quedó por debajo de 6.500. No aumentar/resetear su cuota. La conciliación de
47.024 tokens **ya se aplicó** únicamente al contador diario compartido,
mediante el marcador idempotente `audit:fixtures:2026-11-08`. El archivo privado
`evidencias-locales/auditoria-conversacional/conciliacion-cuota-final-20261108.json`
confirma 84.004 usados, reservas globales en 0, 15.996 restantes y contadores
de usuarios intactos. Las dos fixtures finales añadieron 6.863 tokens sobre
los 40.161 anteriores; no se duplicó lo ya conciliado.

El panel y los límites de Groq siguen siendo la autoridad para el consumo de
la organización; otras llamadas también pueden consumir cuota. El límite
local permanece 100.000/día y 7.000/minuto.

Para una fase adicional expresamente planificada, preservar primero archivos
de `/tmp/evidencias-locales/auditoria-fixture` fuera del contenedor. Como las
fixtures anteriores ya están conciliadas, la vista previa actual es:

```sh
python3 scripts/auditar_fixture.py --prior-fixture-tokens 0 --fourth quincena
```

Añadir `--run` dentro del contenedor ejecuta hasta cuatro POST de IA sobre una
base temporal, incluidos reintentos. No ejecutar solo para volver a obtener
un resultado favorable. Tras conciliar en el origen, no volver a sumar los
mismos 47.024 mediante el parámetro; debe reflejar únicamente consumo pendiente
de incorporar. Actualizar el valor después de nuevas fases del mismo día UTC.

La escritura JSON es atómica, con permisos 0600 y redacción de secretos.
`--self-test` y el modo predeterminado no llaman a API, PostgreSQL o Groq.

## Verificación de esa fase y alcance comprobado

La imagen exacta de esa fase de implementación aprobó **275 casos backend y 97
subpruebas en 46,32 segundos**. El archivo privado
`evidencias-locales/auditoria-conversacional/pruebas-backend-final.txt` conserva
la salida. Hubo una advertencia no bloqueante de deprecación de
Starlette/TestClient con httpx.

También aprobaron **13 casos frontend**, acreditados en
`evidencias-locales/auditoria-conversacional/pruebas-frontend-final.txt`.
Los grupos dirigidos de 24 para respaldo numérico, diez para repetición
limitada y 53 para contexto/intención de ahorro forman parte de las
verificaciones; **no sumarlos como pruebas independientes de la suite**.
La aplicación local quedó levantada con la imagen final.

`evidencias-locales/auditoria-conversacional/aceptacion-final-20261108.json`
registra **58 comprobaciones aprobadas**, 32 filas de reporte y cero llamadas
Groq nuevas. Esta aceptación de API complementa las dos fixtures reales;
no las sustituye ni convierte sus respuestas parciales en correctas.

| Criterio de cierre | Estado al corte |
| --- | --- |
| Listado de metas, prioridad deficitaria y aclaración Q100 | Correctos en rutas deterministas de las fixtures finales. |
| RAG/agentes reales, memoria y fuentes | Hay llamadas reales y evidencia parcial; no reemplazar su validación por las tres salidas deterministas. |
| Guarda numérica contra importes sin respaldo | Implementada; contraste offline real, suite y recorridos finales ejecutados. No certifica relaciones semánticas. |
| Conceptos correctos: pagos frente a recurrentes y selección de deudas | Limitaciones observadas; no equivalen a estar corregidas por validar números. |
| Seguimiento «100/mes → Fondo» | Una llamada; cifras correctas y sin promesa de asequibilidad en el escenario probado. |
| Ausencia de quincenas inventadas | Correcta en la fixture final; la explicación causal sigue siendo parcial. |
| Comparación final 20b/120b con misma revisión/configuración | No completada; no se declara ganador universal. |
| Cuotas, base temporal retirada y origen preservado | Comprobados; 47.024 tokens ya conciliados sin tocar usuarios. |
| Aceptación final de API | 58 comprobaciones, 32 filas y cero llamadas Groq nuevas; aprobada. |
| Suite después de excluir `simulate_goal` de repetición | 275 casos backend, 97 subpruebas y 13 casos frontend aprobados. |

El cierre acredita las preguntas, configuraciones y evidencias descritas.
Las fixtures finales usaron `gpt-oss-120b` con razonamiento medio, salida 768
y hasta tres rondas. No acredita una comparación exhaustiva entre modelos ni
la publicación cloud de estos últimos cambios. Se conservan los fallos y los
límites semánticos: un HTTP 200 no convierte una respuesta incorrecta en aprobada.

## Incidencia posterior del 8 de noviembre: presupuesto de contexto e interfaz

Esta sección corresponde a una revisión posterior al corte anterior. Conserva
sus resultados y contadores como históricos; no los presenta como la validación
de esta corrección ni como el consumo actualizado después de estas llamadas.

Se observaron estos fallos reales en consultas de presupuesto:

| Momento UTC | Recorrido | Resultado observado |
| --- | --- | --- |
| 09:14 | Salud del presupuesto | HTTP 429 después de una llamada y 2.763 tokens; se había ejecutado `financial_diagnosis`. |
| 09:15 | Reintento de salud del presupuesto | HTTP 413 antes del proveedor: cero llamadas nuevas. El diagnóstico repetido ocupaba 5.881 caracteres. |
| 09:15 | Margen disponible | HTTP 429 después de una llamada y 3.272 tokens; se habían consultado panorama y deudas. |

Reiniciar la conversación no resuelve la causa: el contexto necesario para una
sola pregunta también podía exceder el presupuesto. Los 429 y el 413 describen
fallos distintos; no atribuir el segundo a una nueva inferencia de Groq.

La corrección incorpora `backend/context_budget.py` y su integración en el
asistente. El empaquetador comprueba que la estimación del contenido quepa en
6.500 tokens. Si hace falta espacio, retira parejas antiguas de conversación,
usa una versión corta de las instrucciones que conserva reglas y fechas,
compacta los resultados JSON a una fila de detalle con `has_more` y omite
descripciones de herramientas. Conserva sus parámetros: no recorta la pregunta
actual ni cambia el límite de salida de 768 tokens.

El flujo consulta primero presupuesto o margen cuando esa es la pregunta,
antes de incorporar deudas o metas que no sean necesarias. Los esquemas
disponibles se seleccionan para la pregunta actual; inflación se añade solo
si se solicita. La consulta de salud prepara los datos antes de pedir una sola
respuesta al modelo, sin herramientas adicionales en esa llamada. El margen
dispone de respuesta calculada por el backend, con cero llamadas al proveedor.
Si otro paso no cabe o se alcanza un límite de uso o salida, se ofrece una
respuesta de respaldo con cifras verificadas. Esto reduce el contexto y las
rondas; no amplía las cuotas ni convierte un fallo en una respuesta aprobada.

Permanecen los límites compartidos de **7.000 tokens/minuto y 100.000/día**.
La reserva y el control de uso siguen activos. No se recomienda subir ni
reiniciar cuotas para resolver un problema de tamaño del contexto.

La revisión inicial aprobó 50 pruebas dirigidas y nueve subpruebas, incluidas
diez pruebas puras del empaquetador y seis de presupuesto. La verificación
final de la imagen exacta aprobó **307 casos backend y 106 subpruebas en
52,59 segundos**, con una advertencia no bloqueante. La salida está en
`evidencias-locales/auditoria-conversacional/pruebas-contexto-final-20261108.txt`.
También aprobaron los **13 casos frontend y la compilación**. Los grupos
dirigidos forman parte de estas verificaciones; no sumarlos a la suite ni al
total histórico de 275.

La aceptación privada
`evidencias-locales/auditoria-conversacional/aceptacion-contexto-20261108.json`
registra **61 comprobaciones aprobadas, 37 filas de reporte y cero llamadas
Groq nuevas**. La conservación del contexto precargado se comprobó además con
dos regresiones adicionales dentro de un grupo de 13 casos dirigidos.
Una prueba que antes esperaba HTTP 429 ahora comprueba HTTP 200 con un
resumen de cifras verificadas: el paso rechazado permanece auditado con uso
cero y el consumo de pasos anteriores se conserva. La respuesta de respaldo
no oculta consumo ni equivale a una inferencia completada por el proveedor.

La fixture real de presupuesto `3bcdcbdf552c`, iniciada a las **09:23:52 UTC**,
probó «¿Qué tan sano ves mi presupuesto de octubre?». Los primeros tres
turnos de metas usaron las rutas deterministas, sin llamadas al proveedor.
La pregunta de presupuesto obtuvo **HTTP 200, una llamada y 2.479 tokens**.
La respuesta respaldó ingresos de Q7.250, gastos de Q7.177, ahorro de Q0 y
margen de Q73; los gastos representan el 98,99 % de los ingresos. La
comparación con septiembre mantuvo correctamente Q880 más de gastos y Q500
menos de ahorro. Fue una respuesta completa del modelo, sin recurrir a la
respuesta de respaldo de la guarda. El recorrido concreto queda aprobado;
no extiende esa conclusión a todas las preguntas ni a la semántica de las
respuestas históricas.

La evidencia está archivada en
`evidencias-locales/auditoria-fixture-presupuesto-20261108.tar`.
La base temporal se retiró (`dropped=true`), empezó con la cuota predeterminada
de 20.000 y mantuvo intactos los contadores de usuarios del origen.
`evidencias-locales/auditoria-conversacional/conciliacion-presupuesto-20261108.json`
confirma la incorporación de los 2.479 tokens: **49.503 tokens acumulados de
fixtures, 95.032 en el contador global diario y 4.968 restantes**. El contador
observado de Ana fue **63.012/100.000 antes y después**; esa es la configuración
de usuario vigente en este corte y no se modificó su cuota durante esta
comprobación. Los valores anteriores se conservan como cortes históricos.
Las fixtures ya conciliadas no deben volver a sumarse: la reproducción futura
parte de `--prior-fixture-tokens 0`, salvo consumo nuevo pendiente de conciliar.
No se hicieron más llamadas al proveedor para cerrar este registro.

La interfaz local también recibió ajustes ya comprobados visualmente:

- Compromisos pendientes o de arrastre en rojo claro, parciales en amarillo
  y completados en verde. Las metas usan amarillo para progreso, verde para
  cumplida, rojo para vencida y gris para inactiva.
- Acciones de dinero, edición y baja mediante iconos; las bajas usan rojo y
  las ayudas de las acciones están en español y aparecen con ratón o foco.
- La tabla principal de compromisos usa 15 px para sus datos y estados;
  conserva las categorías como información secundaria de 12 px.
- Cada tarjeta de meta despliega sus movimientos debajo de sus acciones,
  con apertura y cierre independientes. Las tarjetas se alinean arriba y
  no se estiran cuando una vecina se abre. La comprobación en navegador
  mostró la meta Computadora con Q1.050 y cuatro movimientos, mientras las
  otras tarjetas conservaron su altura.
- La edición de metas permite eliminarlas con confirmación explícita de que
  la acción es permanente y cambia los totales de ahorro. Seis pruebas
  comprobaron el borrado transaccional de la meta y sus movimientos asociados,
  junto con la auditoría. **No se eliminaron metas reales para probar la UI**.

La captura privada `evidencias-locales/metas-estados-20261108.png` acredita la
revisión visual de los estados de metas. Las capturas adicionales
`evidencias-locales/metas-acordeon-20261108.png`,
`evidencias-locales/meta-edicion-eliminar-20261108.png` y
`evidencias-locales/presupuesto-respuesta-breve-20261108.png` documentan el
acordeón, la acción de borrado y la respuesta breve de presupuesto.
La aplicación local quedó disponible con esta revisión. La suite, la
aceptación y la fixture real de presupuesto ya se ejecutaron; este cierre
conserva los límites semánticos históricos y **no acredita la publicación
cloud de estos cambios**.

## Ajustes de cierre posteriores

Las cifras y conclusiones de cada fase anterior son históricas. El cierre del
8/11 compactó `00_instrucciones.md` como fuente de reglas de ejecución y retiró
repeticiones del prompt; conserva las fuentes recuperadas también en el contexto
compacto. Mantiene razonamiento medio, salida máxima 768 y los topes de cuotas.
El contrato `local_only` permite respuestas calculadas o un resumen de flujo
verificado sin modelo durante una espera; si no hay hechos/ruta suficientes,
explica que necesita IA sin llamar a Groq. Los rechazos distinguen cuota
personal, día, minuto, llamadas y proveedor.

La revisión dirigida de esta compactación aprobó 53 pruebas y cuatro subpruebas
sin llamadas reales. En la misma pregunta de salud de presupuesto, con fecha y hechos idénticos y
proveedor simulado, la entrada estimada pasó de 3.392 a 2.527 tokens (-25,50 %).
La reserva total pasó de 4.160 a 3.295 (-20,79 %), conservando salida 768; no significa que toda pregunta ahorre ese
porcentaje ni demuestra por sí sola la calidad de inferencias nuevas. La suite
completa, publicación y contraste finales se consignan en `estado.md`. No sumar
las pruebas dirigidas a la suite como si fueran casos adicionales.
