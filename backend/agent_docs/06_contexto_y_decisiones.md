# Preguntas de contexto y escenarios

## F33 · ¿La inflación explica que esté gastando más?
Estado: DOCUMENTADA; habilitada si existen `financial_overview`, `spending_breakdown` e `inflation`.
Consulta: intervalos comparables de flujo y `inflation(year)` para un año con dato publicado.
Datos/cálculo: mostrar variación observada y tasa anual oficial disponible, con año, fuente y fecha de consulta. No mezclarlas como si fueran la misma medida.
Criterio: el IPC general es contexto; el gasto personal cambia también por cantidades, composición, fechas y registros. Si no hay dato anual, decirlo; no usar el último dato como si correspondiera al año pedido.
Límite: no calcula inflación personal, ni proyecta precios de compras o metas, ni atribuye causalidad. No aplicar la tasa automáticamente al presupuesto sin simulación explícita.
Respuesta HIPOTÉTICA: “Tus pagos aumentaron en el período comparado; el indicador anual aporta contexto, pero no demuestra que todo ese aumento sea inflación.”
Seguimiento: “¿Quieres revisar qué categorías cambiaron?”

## F34 · ¿Cómo comparo una meta en dólares con mi ahorro en quetzales?
Estado: DOCUMENTADA; habilitada si existen `exchange_rate` y `simulate_goal`; conversión guardada en GTQ no es operación cambiaria.
Consulta: referencia USD/GTQ de Banguat y fecha; confirmar objetivo en USD y pedir cálculo/simulación al backend. Si la conversión no forma parte del resultado calculado, no multiplicarla en texto.
Datos/cálculo: una referencia vigente no es una cotización garantizada; el objetivo registrado y saldos internos permanecen en GTQ.
Criterio: mostrar la fecha y distinguir referencia de compra/venta comercial. Explicar variación futura sin inventar un margen “seguro”.
Límite: `simulate_goal` recibe importes GTQ y no convierte moneda por sí mismo; si falta función de conversión, describir esa limitación o pedir objetivo GTQ confirmado. No inventar tasa ni comisiones.
Respuesta HIPOTÉTICA: “Puedo consultar la referencia, pero para una meta pagadera en USD habrá riesgo cambiario y la tasa de tu proveedor puede diferir.”
Seguimiento: “¿Quieres fijar un objetivo GTQ explícito para el escenario?”

## F35 · ¿Qué hago si recibo un ingreso extra?
Estado: DOCUMENTADA; habilitada si existen `financial_diagnosis` y `budget_scenario`.
Consulta: situación actual y escenario mensual con `monthly_extra_income` confirmado; si es ingreso único, identificar que se está probando solo ese período, sin proyectarlo cada mes.
Datos/cálculo: comparar disponible y una asignación explícita a deuda/ahorro mediante extras separados; no contar dinero esperado como ingreso cobrado.
Criterio: revisar vencidos, reserva y prioridad personal antes de elevar gastos fijos. Distinguir pago extraordinario de aumento estable.
Límite: el escenario aplica cambios al período base y no modela recurrencia futura; un premio no financia por sí mismo un compromiso mensual indefinido.
Respuesta HIPOTÉTICA: “Podemos probar ese extra una sola vez y elegir entre pendientes y ahorro; no aumentaría gastos fijos basándome solo en ese ingreso.”
Seguimiento: “¿Ya lo recibiste y se repetirá o es único?”

## F36 · ¿Cómo me preparo si mis ingresos podrían bajar?
Estado: DOCUMENTADA; cobertura parcial: herramientas de flujo y metas; reducción de ingreso NO es argumento de `budget_scenario`.
Consulta: `financial_diagnosis` de un mes representativo; identificar compromisos flexibles y reserva disponible confirmada.
Datos/cálculo: no pasar importes negativos a `monthly_extra_income` ni fabricar un escenario de caída no soportado. Puede simularse una reducción de gasto explícita por separado, sin llamarla prueba completa de pérdida de ingreso.
Criterio: preparar inventario de esenciales, reserva y gastos posponibles; distinguir una posibilidad de un despido confirmado.
Límite: no existe campo de saldo de caja ni motor de duración de reservas. No dar meses exactos de supervivencia sin cálculo backend y datos suficientes.
Respuesta HIPOTÉTICA: “Podemos revisar compromisos y reservas; el escenario actual no calcula una caída de ingreso. No te daré una proyección inventada.”
Seguimiento: “¿Qué ingreso podría cambiar y qué recursos líquidos tienes fuera de Saldo?”

## F37 · ¿Cómo distingo un mes excepcional de un problema habitual?
Estado: DOCUMENTADA; habilitada para comparación si existen `financial_overview` y `spending_breakdown`.
Consulta: dos o tres meses cerrados, mismos criterios de fechas; confirmar qué compras fueron excepcionales.
Datos/cálculo: mostrar resultados de cada mes y cambios que ya devuelve el backend; no inventar tendencia estadística, promedio ni regresión.
Criterio: un gasto médico puntual o compra grande puede cambiar un mes. Revisar también si la captura de datos mejoró en el período más reciente.
Límite: no deducir recurrencia por títulos similares ni predecir el siguiente mes a partir de pocos puntos. Un mes excepcional no justifica ignorar su efecto en caja.
Respuesta HIPOTÉTICA: “El gasto fuerte aparece en un solo cierre y tú indicas que no se repetirá; conviene separarlo del patrón, manteniendo su impacto real en ese mes.”
Seguimiento: “¿Qué partida volverá a aparecer y cuál fue única?”

## F38 · ¿Debo seguir la regla 50/30/20?
Estado: DOCUMENTADA; guía conceptual; clasificación completa y comparación de esa regla NO implementadas.
Consulta: `financial_overview` y `spending_breakdown` como contexto, no como aplicación automática de la regla.
Datos/cálculo: Saldo no clasifica necesidades/deseos ni separa perfectamente servicio de deuda, consumo y principal. No afirmar cumplimiento sumando categorías ambiguas.
Criterio: es una referencia adaptable, no un estándar obligatorio. Ajustarla a ingresos, vivienda, salud y obligaciones concretas; una guía que no cabe en la realidad debe revisarse, no utilizarse para culpar. Fuente: CFPB en documento 08.
Límite: hay variantes sobre dónde ubicar pagos de deuda; indicar la convención antes de comparar y calcular en backend si se desarrolla la función.
Respuesta HIPOTÉTICA: “Puede servir como orientación, pero primero necesitamos clasificar tus gastos contigo; tus porcentajes actuales de egreso/ahorro no son esa regla.”
Seguimiento: “¿Quieres identificar qué gastos consideras esenciales?”

## F39 · ¿Cuáles de mis gastos son necesidades y cuáles deseos?
Estado: DOCUMENTADA; habilitada para inventario si existe `spending_breakdown`; clasificación automática NO implementada.
Consulta: ranking y, si es pertinente, plantillas recurrentes.
Datos/cálculo: categorías e importes; no existe etiqueta estructurada de necesidad, bienestar o prioridad personal.
Criterio: preguntar por función y alternativa: transporte al trabajo, tratamiento y conectividad de estudio pueden ser necesarios aunque el nombre parezca flexible. Separar necesidad de modalidad elegida sin asumir que exista alternativa más barata viable.
Límite: no etiquetar toda comida fuera, ocio o internet como desperdicio ni hacer diagnósticos psicológicos de compra.
Respuesta HIPOTÉTICA: “Internet puede ser esencial para tu estudio; revisaría el plan y el uso antes de proponer cancelarlo. La categoría por sí sola no responde eso.”
Seguimiento: “¿Qué gasto podrías cambiar sin afectar salud, trabajo o estudio?”

## F40 · ¿Puedo asumir un nuevo gasto mensual?
Estado: DOCUMENTADA; cobertura parcial: `financial_diagnosis` y `budget_scenario`; nuevo consumo no es un argumento directo del escenario.
Consulta: flujo representativo, vencimientos y recurrentes. No usar `monthly_extra_debt` para un gasto que no sea deuda ni `monthly_extra_savings` para consumo.
Datos/cálculo: el contrato actual no simula nuevos gastos de consumo. Mostrar margen registrado y compromisos; indicar la función pendiente si se necesita un disponible recalculado.
Criterio: evaluar estabilidad, gastos omitidos, prioridades y condición de salida; no decidir por el usuario ni presentar saldo positivo como autorización de compra.
Límite: no reservar dinero ni contratar servicio. Para préstamo nuevo también faltan condiciones y costo total, véase F24.
Respuesta HIPOTÉTICA: “Hay margen registrado, pero falta contrastar el nuevo consumo y gastos no cargados; el escenario actual no incluye ese tipo de incremento.”
Seguimiento: “¿Cuál sería el costo completo, desde cuándo y podrías cancelarlo?”
