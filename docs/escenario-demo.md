# Escenario financiero de demostración: Ana

Este documento describe la carga inicial de datos ficticios para `demo@example.test`
(Ana), con corte histórico **2 de noviembre de 2026**. Septiembre y octubre son
meses completos; noviembre es un mes parcial. Todos los importes son GTQ. Los
nombres visibles se normalizaron para que la interfaz se lea como un producto;
los datos continúan siendo ficticios. No es una fotografía de los saldos actuales.

La carga se encuentra en `backend/demo.py`, se realiza explícitamente con `python -m backend.demo` y exige `APP_ENV=local`. No se ejecuta al arrancar el servicio. No llama a Groq, no genera consumo de IA y no publica datos en Neon, Render ni Power BI. Las preguntas posteriores sí consumen la cuota de IA configurada.

## Ediciones posteriores legítimas

En el ensayo local del **8 de noviembre**, después de operaciones del usuario,
se observaron ingresos noviembre Q6.000, pagos Q2.277, ahorro neto Q1.275 y flujo
Q2.448. El préstamo familiar quedó completamente pagado (Q900 previstos y
Q900 ejecutados). El saldo de la meta computadora pasó a Q1.050; el fondo de
emergencia conserva Q550. Octubre sigue en Q7.250/Q7.177/Q0/Q73. La deuda
pendiente al corte 8/11 es Q7.350; al corte anterior al pago del 8/11 puede ser
Q7.900. Son cambios válidos, no errores que deban revertirse para coincidir
con la semilla. Consultar siempre los saldos vigentes y el corte requerido.

## Contexto que explican los registros

Ana trabaja en un empleo administrativo, recibe un sueldo fijo de Q6.000 y complementa sus ingresos con trabajos de diseño gráfico. Estudia en la universidad, alquila vivienda y mantiene tres compromisos de deuda. Los ingresos independientes varían: Q900 cobrados en septiembre y Q1.250 en octubre. En noviembre existe un posible cobro de Q700 que todavía **no es ingreso realizado**.

Sus gastos esenciales absorben gran parte del ingreso. Las cenas por aplicación, cafés, snacks, taxis y compras pequeñas aumentan en octubre. Aunque cobra Q350 más que en septiembre, termina octubre con un flujo disponible menor. Además, retira Q300 del fondo de emergencia mientras sigue aportando a otras metas: hay una oportunidad de revisar prioridades y reducir la dispersión del ahorro.

La historia no incluye cuentas bancarias, patrimonio completo, tasas de interés, ingresos futuros garantizados ni contratos crediticios. No se deben completar esos datos con suposiciones.

## Tamaño y estados del conjunto

Sobre la semilla original limpia, una carga completa deja:

| Entidad | Cantidad | Qué permite probar |
|---|---:|---|
| Categorías | 15 | Ingreso fijo, ingreso variable y trece clases de egresos |
| Obligaciones | 184 | Pagadas, parcialmente pagadas, previstas sin pagos y una anulada |
| Pagos | 177 | Movimientos diarios, abonos múltiples y agregación por fecha de pago |
| Plantillas recurrentes | 8 | Siete activas y una inactiva |
| Metas | 6 | En progreso, cumplida, vencida sin ahorro y pospuesta/inactiva |
| Movimientos de ahorro | 12 | Aportes y retiros, sin saldo negativo cronológico |

Son **181 obligaciones, 174 pagos, 12 categorías, ocho plantillas, cinco metas y once movimientos de ahorro nuevos**. Los registros creados manualmente en demostraciones anteriores se conservan y se suman a estas cifras. La aplicación devuelve los contadores efectivos al terminar la carga.

Las plantillas activas empiezan el **1 de diciembre de 2026**. Esto evita duplicar obligaciones de noviembre ya registradas, incluidas las de la semilla original. Al abrir diciembre se crean siete partidas; volver a abrirlo conserva esas mismas siete. La plantilla de gimnasio está inactiva y no genera partidas.

## Conciliación de los meses

La fórmula es:

`disponible del período = ingresos cobrados − egresos pagados − ahorro neto`

`ahorro neto = aportes a metas − retiros de metas`

| Período | Ingresos cobrados | Egresos pagados | Ahorro neto | Disponible |
|---|---:|---:|---:|---:|
| Septiembre completo | Q6.900 | Q6.297 | Q500 | Q103 |
| Octubre completo | Q7.250 | Q7.177 | Q0 | Q73 |
| 1–2 de noviembre, semilla limpia | Q6.000 | Q1.677 | Q625 | Q3.698 |

**Disponible es flujo del período, no saldo bancario ni dinero libre para gastar.** En noviembre quedan alquiler, universidad, servicios, salud, suscripciones y otros compromisos sin pagar. No se debe recomendar destinar Q3.698 íntegros a una deuda o meta sin revisar esos pendientes.

La demostración previa añadió el registro hoy visible como «Material de estudio», Q200 previstos y un abono de Q50. Si ese registro está presente, noviembre tiene Q1.727 de egresos realizados y Q3.648 de disponible; conserva además Q150 pendientes. Los resultados deben obtenerse del backend, no copiarse de esta tabla.

## Comparación por categoría

| Categoría | Septiembre | Octubre |
|---|---:|---:|
| Vivienda | Q1.500 | Q1.500 |
| Alimentación | Q900 | Q1.000 |
| Universidad | Q900 | Q900 |
| Deudas: pagos realizados | Q750 | Q750 |
| Cafés y snacks | Q336 | Q570 |
| Comida a domicilio | Q348 | Q520 |
| Transporte: bus y taxis | Q284 | Q384 |
| Servicios básicos | Q325 | Q345 |
| Internet y telefonía | Q320 | Q320 |
| Compras pequeñas | Q176 | Q280 |
| Salud | Q120 | Q250 |
| Entretenimiento | Q180 | Q200 |
| Suscripciones | Q158 | Q158 |
| **Total** | **Q6.297** | **Q7.177** |

La vivienda es la mayor categoría en ambos meses; cafés y snacks son la mayor de las categorías discrecionales de octubre, seguidos de comida a domicilio. Café/snacks + comida a domicilio + compras pequeñas + taxis suman Q1.000 en septiembre y Q1.610 en octubre: **Q610 más, un 61%**. Esta agrupación sirve para analizar oportunidades; no significa que cada transacción sea innecesaria ni que todo transporte pueda eliminarse.

## Deudas: principal, pagos y saldo

Los tres compromisos usan la categoría exacta **Deudas**. Cada uno existe como una sola obligación; sus abonos de septiembre y octubre son pagos vinculados a ella. No hay obligaciones adicionales que vuelvan a contabilizar esas mismas cuotas como principal.

| Compromiso ficticio | Total registrado | Pagos acumulados | Saldo pendiente |
|---|---:|---:|---:|
| Préstamo familiar | Q900 | Q350 | Q550 |
| Compra de computadora | Q2.500 | Q450 | Q2.050 |
| Préstamo personal | Q6.000 | Q700 | Q5.300 |
| **Total** | **Q9.400** | **Q1.500** | **Q7.900** |

Sus fechas de referencia son el 30 de noviembre. El modelo registra saldos
manuales sin un cronograma contractual; las etiquetas visibles no sustituyen
las condiciones del préstamo. **El sistema no dispone del calendario contractual ni de las cuotas mínimas, y Q7.900 no representa una cuota mensual.** El egreso registrado por deudas es Q750 en septiembre y Q750 en octubre.

El orden ilustrativo de bola de nieve sería Q550 → Q2.050 → Q5.300, sujeto primero a confirmar mínimos, vencimientos reales, capacidad de pago y posibles penalizaciones. No es posible recomendar el método de avalancha con precisión porque faltan las tasas.

El ratio observable de pagos de deuda sobre ingreso cobrado es Q750/Q6.900 = **10,87%** en septiembre y Q750/Q7.250 = **10,34%** en octubre. Debe llamarse ratio de pagos **registrados**, no ratio contractual completo ni diagnóstico definitivo de solvencia.

## Metas y decisiones interesantes

| Meta | Objetivo | Saldo al corte | Fecha objetivo | Estado |
|---|---:|---:|---|---|
| Fondo de emergencia | Q5.000 | Q550 | 30/04/2027 | Activa |
| Computadora para trabajo freelance | Q4.500 | Q400 | 28/02/2027 | Activa |
| Diplomado para mejorar ingresos | Q1.800 | Q150 | 31/01/2027 | Activa |
| Viaje pospuesto | Q1.200 | Q0 | 31/08/2027 | Inactiva |
| Curso corto completado | Q25 | Q25 | 30/11/2026 | Cumplida, activa |
| Renovación de equipo · plazo vencido | Q600 | Q0 | 31/10/2026 | Vencida, activa |

Las dos últimas metas permiten comprobar que «activa» no significa «pendiente alcanzable»: el curso ya tiene el objetivo cubierto y no necesita otro aporte; la renovación está vencida y requiere revisar su fecha o prioridad con el usuario. El curso recibe Q25 el 2 de noviembre y la meta vencida no tiene movimientos. Los fondos de metas suman Q1.125; no representan ingresos nuevos ni deben sumarse al flujo disponible.

El retiro de Q300 del fondo de emergencia ocurre el 20 de octubre y el retiro de Q50 de la meta de viaje ocurre el 21 de octubre. Ninguno produce sobregiro. Ahorrar y retirar dinero son transferencias entre disponible y fondos, no consumo duplicado.

Los compromisos de deuda por una computadora y la meta de comprar otra computadora pueden indicar una duplicación de prioridades. El asesor debe preguntar si se trata de equipos distintos o si conviene reutilizar/reparar el actual antes de seguir destinando ahorro a esa meta. Los nombres por sí solos no prueban una compra redundante.

Una reducción hipotética del 25% de cafés/snacks, 25% de comida a domicilio y 50% de compras pequeñas de octubre liberaría Q142,50 + Q130 + Q140 = **Q412,50 mensuales** si ese comportamiento pudiera sostenerse. Es una simulación sobre un mes observado, no una promesa. Antes de asignarla a una meta o deuda, hay que revisar compromisos pendientes e ingresos variables.

## Preguntas de aceptación

Las cifras siguientes corresponden a la carga original. Para un corte posterior,
comprobar herramientas actuales y aplicar las ediciones legítimas indicadas arriba.

| Pregunta del usuario | Qué debe comprobar una respuesta correcta |
|---|---|
| ¿En qué gasto más? | Pedir o declarar período; ordenar pagos de egresos por categoría. Octubre: vivienda Q1.500. No mezclar principal de deuda o previsiones con consumo realizado. |
| ¿Por qué no me alcanza si gané más? | Comparar septiembre y octubre completos: ingreso +Q350, gasto +Q880 y ahorro neto −Q500; disponible Q103 → Q73. |
| ¿Dónde tengo gastos hormiga? | Examinar frecuencia, importes y títulos de cafés, snacks, compras pequeñas, delivery y taxis; cuantificar y presentar candidatos, sin juzgar necesidades personales. |
| ¿Cuánto debo en total? | Consultar compromisos Deudas y todos sus abonos: Q7.900, no sumar obligaciones de otras categorías como si fueran préstamos. |
| ¿Qué deuda podría terminar primero? | Ordenar por saldo: Q550, Q2.050, Q5.300; solicitar mínimos/tasas/vencimientos para un plan completo. |
| ¿Puedo destinar todo mi disponible a mis deudas? | Revisar compromisos previstos pendientes antes de responder; el disponible parcial de noviembre todavía debe cubrir pagos futuros. |
| ¿Cuánto ahorro realmente? | Septiembre Q500 netos y octubre Q0; mostrar aportes y retiros, sin llamar gastos a las transferencias de ahorro. |
| ¿Cómo voy con mis metas? | Leer las seis metas, distinguir en progreso, cumplida, vencida e inactiva, saldos y fechas; comparar necesidad de ahorro mensual con capacidad sostenible. |
| ¿Puedo alcanzar todas mis metas sin cambios? | No prometerlo: hay poca holgura en meses completos, deuda pendiente y metas simultáneas. Simular prioridades y reducciones cuantificadas. |
| ¿Qué pagos se repetirán? | Consultar plantillas, estado y fecha de inicio: siete activas desde diciembre; gimnasio inactivo. No confundir plantilla con pago ya realizado. |
| ¿Noviembre mejoró respecto a octubre? | Advertir que noviembre solo incluye dos días y que varias facturas no se han pagado; comparar períodos equivalentes o proyectar con supuestos visibles. |
| ¿Ya cobré los Q700 de freelance de noviembre? | No: es una obligación de ingreso prevista sin pagos. |
| ¿Qué puedo hacer para ordenar mis finanzas? | Partir de los datos, priorizar esenciales y compromisos, revisar gastos discrecionales y suscripciones, separar ingresos estables de variables y plantear una meta inicial alcanzable. |

## Seguridad de la carga y normalización

La carga es transaccional: una excepción revierte las inserciones y la normalización. Bloquea la fila de Ana y registra `demo_seed_v1` en auditoría; ejecuciones posteriores devuelven los contadores sin volver a crear el escenario. No cambia contraseñas, límites de tokens, historial de consultas, configuración de servicios ni datos de otros usuarios.

La semilla antigua colocó tres pagos y un aporte de ahorro el 5 de noviembre. La ampliación corrige **solo la fecha del primer movimiento original que coincida con título, importe y fecha exactos**: sueldo Q6.000, alimentación Q1.000, universidad Q400 y aporte al fondo de emergencia Q500, al **1 de noviembre**. Conserva IDs e importes. Registra el número de cambios en la acción `demo_normalize_dates_v1`. No modifica pagos posteriores añadidos por el usuario, aunque coincidan en importe y fecha.

Si la cuenta ya tiene otros movimientos futuros, la salida los declara en `existing_future_movements`; no los elimina ni los corrige silenciosamente. Antes de cargar el escenario en la cuenta local existente se conserva una copia de seguridad privada. Las pruebas automatizadas se ejecutan en una base aleatoria temporal y verifican idempotencia, conciliación, aislamiento, estados, fechas, ahorro sin sobregiro y reversión ante fallos.
