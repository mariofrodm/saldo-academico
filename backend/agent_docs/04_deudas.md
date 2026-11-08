# Preguntas sobre deuda y compromisos pendientes

## F17 · ¿Cuánto debo y qué está vencido?
Estado: DOCUMENTADA; habilitada si existen `debt_snapshot` y `obligations_snapshot`.
Consulta: ambas al mismo `as_of`; la primera incluye solo egresos de categoría exacta Deudas, sin distinguir mayúsculas. La segunda incluye todos los compromisos de gasto pendientes.
Datos/cálculo: totales de pendiente, vencido, vence hoy y futuro, más detalle y `has_more`; pagos futuros no reducen el saldo al corte.
Criterio: distinguir deuda identificada de servicios/compras pendientes. “Vencido” significa vencimiento pasado y pendiente en registros, no mora contractual certificada.
Límite: no hay saldo bancario, intereses devengados ni historial de modificaciones; títulos no clasifican créditos. No sumar cuota y saldo global del mismo crédito dos veces.
Respuesta HIPOTÉTICA: “En Deudas hay Q2.000 pendientes; aparte hay servicios pendientes. Debemos confirmar que Deudas contiene saldos completos y no solo cuotas.”
Seguimiento: “¿Esos registros representan saldos o cuotas mensuales?”

## F18 · ¿Cómo aplico la bola de nieve?
Estado: DOCUMENTADA; habilitada para orden por saldo si existe `debt_snapshot`; plan contractual incompleto.
Consulta: `debt_snapshot(as_of)`, que ordena de menor a mayor pendiente de Deudas; revisar flujo con `financial_overview` antes de proponer aporte adicional.
Datos/cálculo: usar orden y saldos devueltos; no inventar cuotas mínimas.
Criterio: la bola de nieve concentra el extra en el saldo menor mientras se atienden las obligaciones requeridas de los demás; al liquidarlo se redirige ese pago. Puede motivar avances, sin garantizar menor interés total. Fuente: guía de reducción de deuda CFPB, documento 08.
Límite: confirmar saldos completos, mínimos y condiciones. No recomendar omitir obligaciones urgentes por seguir el orden mecánicamente.
Respuesta HIPOTÉTICA: “El registro menor sería candidato para empezar. Antes de fijar el extra, confirma los mínimos del resto y el dinero realmente disponible.”
Seguimiento: “¿Conoces los pagos exigidos y algún atraso que deba atenderse primero?”

## F19 · ¿Me conviene bola de nieve o avalancha?
Estado: DOCUMENTADA; explicación conceptual disponible; comparación numérica de intereses NO implementada.
Consulta: `debt_snapshot(as_of)` para saldos; preguntar tasas y mínimos que Saldo no almacena. No inventar un orden de avalancha desde el nombre del acreedor.
Datos/cálculo: no existe motor de amortización contractual ni campo APR.
Criterio: avalancha prioriza la deuda con tasa más alta y puede reducir costo; bola de nieve prioriza la menor y puede facilitar constancia. La elección requiere también restricciones y preferencias. Fuente: CFPB en documento 08.
Límite: sin tasas, periodicidad y comisiones no se cuantifica cuál ahorra más ni se promete salir más rápido.
Respuesta HIPOTÉTICA: “Puedo ordenar los saldos para bola de nieve, pero aún no comparar el costo de avalancha: faltan tasas y mínimos contractuales.”
Seguimiento: “¿Quieres empezar con el inventario de datos que debemos confirmar?”

## F20 · ¿Cuándo quedaré libre de deudas?
Estado: DOCUMENTADA; cobertura parcial: inventario y capacidad; calendario de amortización NO implementado.
Consulta: `debt_snapshot(as_of)`, flujo mensual y `budget_scenario` para un extra explícito.
Datos/cálculo: el escenario evalúa capacidad de flujo, no evolución de principal/intereses. No dividir saldo entre aporte y presentar el resultado como plazo contractual.
Criterio: explicar qué puede hacerse hoy y qué falta: saldos completos a fecha, tasas, mínimos, comisiones, nuevas compras y periodicidad.
Límite: la herramienta no estima fecha de liquidación de préstamos ni ahorro de intereses. Un saldo de compromiso puede ser una cuota y no el capital total.
Respuesta HIPOTÉTICA: “Podemos probar si Q200 extra caben en tu mes base; no puedo dar una fecha fiable de liquidación con los datos actuales.”
Seguimiento: “¿El saldo registrado incluye toda la deuda y tienes el detalle del contrato?”

## F21 · ¿Cuál es mi ratio de endeudamiento?
Estado: DOCUMENTADA; DTI formal NO calculable con el esquema actual.
Consulta: `spending_breakdown(start,end)` para pagos de Deudas/ingreso registrado; `debt_snapshot(as_of)` aporta pendientes, que NO se usan como numerador mensual.
Datos/cálculo: DTI convencional = pagos mensuales requeridos de deudas / ingreso mensual bruto × 100; faltan esas cuotas e ingreso bruto. Si runtime devuelve `debt_payments` y `debt_payments_to_observed_income_percent`, es una aproximación de pagos ejecutados en categoría Deudas/ingreso registrado. `expense_to_income_percent` incluye todos los egresos y tampoco es DTI. Fuente: CFPB en documento 08.
Criterio: ofrecer la aproximación con ese nombre, período y cobertura si está disponible; explicar por qué no calcula el DTI formal. Con ingreso cero el porcentaje es no calculable.
Límite: no aplicar umbral universal ni declarar aprobación/rechazo crediticio. Una aproximación no sustituye el indicador del prestamista.
Respuesta HIPOTÉTICA: “Tengo tu proporción de egresos registrados, pero no el DTI: faltan ingreso bruto y pagos mensuales exigidos.”
Seguimiento: confirmar esos dos datos antes de evaluar capacidad crediticia.

## F22 · ¿Pago deudas o ahorro primero?
Estado: DOCUMENTADA; habilitada si existe `financial_diagnosis`; escenarios requieren `budget_scenario` y, para una meta, `savings_plan`.
Consulta: último mes cerrado representativo, pendientes al corte y metas actuales. Comparar una asignación explícita de extra a deuda y ahorro sin usar dos veces el mismo excedente.
Datos/cálculo: escenario con `monthly_extra_debt` y `monthly_extra_savings`; no sumar aportes base ya incluidos en ahorro neto.
Criterio: revisar esenciales, vencidos, colchón para imprevistos y condiciones de deuda antes de elegir. Evitar dejar al usuario sin recursos para urgencias básicas.
Límite: sin tasas y contratos no hay optimización de interés ni regla universal de asignación.
Respuesta HIPOTÉTICA: “Podemos comparar un reparto prudente del extra; no asignaría todo a la deuda si eso te obliga a endeudarte ante cualquier imprevisto.”
Seguimiento: “¿Qué reserva de emergencia tienes realmente disponible?”

## F23 · No me alcanza para pagar, ¿qué hago?
Estado: DOCUMENTADA; habilitada para diagnóstico si existen `financial_overview` y `obligations_snapshot`.
Consulta: flujo y vencimientos al corte; verificar que los ingresos estén completos.
Datos/cálculo: déficit registrado y pendientes; no calcular capacidad desde títulos ni proponer un importe que la herramienta no respalde.
Criterio: identificar esenciales y una cantidad sostenible; sugerir contactar directamente al acreedor antes de comprometer pagos y solicitar opciones por escrito. Guías de referencia de CFPB y consumer.gov en documento 08.
Límite: no recomendar dejar de pagar de forma general, contratar nuevo crédito, pagar gestores o aceptar acuerdos sin conocer costo. La aplicación no negocia ni determina consecuencias legales en Guatemala.
Respuesta HIPOTÉTICA: “El registro no deja margen suficiente. Primero confirmemos los datos y qué es esencial; después podrías comunicar al acreedor lo que sí puedes sostener.”
Seguimiento: “¿Qué obligación vence primero y ya hablaste con quien te cobra?”

## F24 · ¿Consolido deudas o pido otro préstamo?
Estado: DOCUMENTADA; comparación de productos financieros NO implementada.
Consulta: `financial_diagnosis` para explicar capacidad registrada. Solicitar condiciones completas de las alternativas sin credenciales ni números de cuenta.
Datos/cálculo: Saldo no calcula costo financiero total, amortización ni tasa efectiva de una oferta.
Criterio: comparar costo total, comisiones, plazo, garantías y efecto en pago mensual antes de decidir; cuota menor puede extender pagos. No recomendar productos concretos ni afirmar que nuevo crédito resuelve el déficit.
Límite: una propuesta comercial no es dinero confirmado. Sin información verificable solo puede ofrecerse una lista de aspectos a revisar, no una recomendación personalizada de contratación.
Respuesta HIPOTÉTICA: “No basta con que la cuota sea menor; falta conocer cuánto pagarías en total y durante cuánto tiempo. Hoy puedo mostrarte el flujo registrado.”
Seguimiento: “¿Quieres identificar qué datos de cada oferta faltan para compararlas?”
