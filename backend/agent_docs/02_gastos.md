# Preguntas sobre gastos y hábitos

## F01 · ¿En qué gasto más?
Estado: DOCUMENTADA; habilitada si existe `spending_breakdown`.
Consulta: `spending_breakdown(start,end)`; por ejemplo octubre cerrado: `2026-10-01` a `2026-10-31`. Para “este mes” usa noviembre 1–2 si hoy es 2 de noviembre, y declara que está incompleto.
Datos/cálculo: ranking de pagos por categoría, importe, número de pagos y porcentaje del gasto calculados por backend. Usa `items`, `total_expense` y `has_more`; los totales pueden incluir más detalle del mostrado.
Criterio: identifica las primeras categorías y distingue peso alto de posibilidad de recorte. No suma previstos ni ahorros al consumo.
Límite: categoría no es comercio; registros manuales no prueban cobertura bancaria completa.
Respuesta HIPOTÉTICA: “En octubre, Vivienda lidera con Q1.800; es un gasto grande, pero revisaría primero las categorías flexibles antes de reducir vivienda.”
Seguimiento: “¿Quieres comparar con el mes anterior o revisar gastos pequeños?”

## F02 · ¿Cuáles son mis gastos recurrentes?
Estado: DOCUMENTADA; habilitada si existe `recurring_snapshot`.
Consulta: `recurring_snapshot()`; separar `kind=expense`, activas, inactivas y `start_month` futuro.
Datos/cálculo: `totals` contiene importes mensuales previstos por naturaleza/estado; `items` muestra plantillas, no pagos.
Criterio: explicar compromisos configurados, detectar servicios revisables y confirmar su uso. No sumar una plantilla y su instancia mensual como dos gastos.
Límite: compras repetidas sin plantilla no aparecen aquí. Una plantilla inactiva conserva historia; una activa no acredita pago.
Respuesta HIPOTÉTICA: “Tienes alquiler e internet como plantillas activas; la membresía inactiva no entra en el total activo. Son importes previstos, no egresos ya pagados.”
Seguimiento: “¿Hay suscripciones o pagos periódicos que todavía no registraste?”

## F03 · ¿Tengo gastos hormiga?
Estado: DOCUMENTADA; habilitada si existe `small_expenses`.
Consulta: `small_expenses(start,end,threshold="50.00")`, aclarando que Q50 es un umbral de revisión elegido y modificable.
Datos/cálculo: cantidad e importe de pagos individuales pequeños por categoría, total candidato y porcentaje del gasto excluyendo Deudas, calculados por backend.
Criterio: importe pequeño + repetición + baja prioridad confirmada pueden revelar una oportunidad. Revisar café, snacks o entregas solo si el usuario los considera flexibles.
Límite: un medicamento, pasaje o abono parcial puede ser pequeño y necesario. El total candidato no es ahorro recuperable. La función agrupa pagos; no identifica comercios ni motivaciones.
Respuesta HIPOTÉTICA: “Hay Q420 en pagos de hasta Q50; son candidatos a revisar, no Q420 que debas eliminar. ¿Cuáles aportan poco valor para ti?”
Seguimiento: confirmar umbral, necesidad y un cambio viable antes de simular.

## F04 · ¿Cómo reduzco gastos sin afectar lo esencial?
Estado: DOCUMENTADA; habilitada si existen `spending_breakdown`, `small_expenses` y `budget_scenario`.
Consulta: ranking y candidatos del último mes cerrado; después simular una reducción mensual que el usuario considere viable. En `budget_scenario`, dejar en `"0.00"` los demás cambios si no se proponen.
Datos/cálculo: importes observados y disponible del escenario; el backend verifica que la reducción no supere el gasto registrado.
Criterio: elegir una o dos acciones reversibles: menos pedidos, límite de compras impulsivas o revisar una suscripción. Proteger alimentación suficiente, salud y transporte necesario.
Límite: categorías no clasifican automáticamente necesidades/deseos. No afirmar que reducir todo el total candidato sea posible.
Respuesta HIPOTÉTICA: “Podemos probar un recorte de Q150 que tú confirmes viable y ver su efecto. No reduciría medicinas por aparecer entre los pagos pequeños.”
Seguimiento: “¿Qué gasto estarías dispuesto a cambiar durante un mes?”

## F05 · ¿Gasté más que antes?
Estado: DOCUMENTADA; habilitada si existen `financial_overview` y `spending_breakdown`.
Consulta: `financial_overview(start,end)` y rankings de ambos intervalos si se necesita explicar categorías. La comparación automática usa el período previo de IGUAL NÚMERO DE DÍAS, no necesariamente el mes calendario anterior.
Datos/cálculo: `current`, `previous`, `changes_gtq` y sus fechas. Para septiembre frente a octubre, consultar cada mes explícitamente; no renombrar el intervalo automático.
Criterio: mostrar diferencia que devuelva el backend y revisar pagos excepcionales/fechas.
Límite: un aumento no prueba cambio de hábito ni efecto inflacionario; puede ser una compra única, más registros o cambio en fecha de pago. No calcular porcentajes de cambio si no los devuelve una función.
Respuesta HIPOTÉTICA: “El período consultado muestra Q200 más de egresos que el intervalo previo indicado. Conviene revisar si corresponde a un pago puntual.”
Seguimiento: elegir comparación calendario o por días equivalentes.

## F06 · ¿Por qué el gasto del mes no coincide con mis compromisos?
Estado: DOCUMENTADA; habilitada si existen `financial_overview` y `obligations_snapshot`.
Consulta: flujo por fechas de pago del mes y pendientes al mismo corte (`as_of`).
Datos/cálculo: ejecutado es dinero cobrado/pagado en ese período; pendiente es previsto menos pagos hasta el corte. Un pago de deuda antigua cuenta en el mes del pago, aunque su vencimiento sea anterior.
Criterio: explicar con un compromiso concreto y evitar sumar ejecutado + importe previsto como si fueran gastos distintos.
Límite: los pendientes incluyen vencimientos futuros; el sistema no reconstruye versiones anteriores de títulos/importes. No prometer conciliación bancaria.
Respuesta HIPOTÉTICA: “El compromiso es Q900 y has abonado Q400; Q500 siguen pendientes. El gasto ejecutado incluye solo los abonos con fecha dentro del intervalo.”
Seguimiento: “¿Buscabas saber cuánto pagaste o cuánto debes reservar?”

## F07 · ¿Qué suscripciones podría revisar?
Estado: DOCUMENTADA; habilitada si existen `recurring_snapshot` y `spending_breakdown`.
Consulta: plantillas activas y pagos del mes cerrado; revisar títulos visibles sin inferir que toda categoría Ocio es suscripción.
Datos/cálculo: importe previsto mensual, estado, comienzo e importe pagado por categoría. No existe métrica de uso ni relación bancaria del cargo.
Criterio: preguntar frecuencia de uso, alternativa ya disponible y condición de cancelación. Elegir una candidata concreta antes de cuantificar un escenario.
Límite: no cancelar desde el agente, no asumir reintegro, ausencia de penalidad o que inactivar plantilla cancele el contrato externo. No garantizar un ahorro anual sin duración confirmada.
Respuesta HIPOTÉTICA: “La plantilla Música merece revisión si no la usas. Desactivarla aquí detendría nuevas instancias; la cancelación del servicio se gestiona aparte.”
Seguimiento: “¿La usaste este mes y puedes cancelarla sin costo?”

## F08 · ¿Los muchos pagos pequeños explican mi problema?
Estado: DOCUMENTADA; habilitada si existen `small_expenses` y `spending_breakdown`.
Consulta: mismo período y umbral; contrastar `candidate_total`/`candidate_share_percent` con el ranking general.
Datos/cálculo: `small_expenses` excluye Deudas; su porcentaje usa el gasto sin esa categoría. `spending_breakdown` incluye todos los egresos, por lo que los denominadores difieren.
Criterio: dimensionar el problema antes de dar consejos. Un costo fijo alto o caída de ingresos puede pesar más que cafés. No avergonzar al usuario ni atribuir causalidad a la cantidad de pagos.
Límite: el número de pagos puede aumentar por abonos parciales. La función no agrupa transacciones de un comercio ni detecta automáticamente duplicados.
Respuesta HIPOTÉTICA: “Los pagos pequeños representan una parte acotada del gasto sin deuda; conviene revisar también el compromiso fijo mayor. No todo el déficit se explica por ellos.”
Seguimiento: “¿Prefieres revisar compromisos fijos o elegir un límite para compras pequeñas?”
