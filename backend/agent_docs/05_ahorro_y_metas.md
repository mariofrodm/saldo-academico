# Preguntas sobre ahorro y metas

## F25 · ¿Qué me puedes decir de mis planes de ahorro?
Estado: DOCUMENTADA; habilitada si existe `goal_snapshot`.
Consulta: `goal_snapshot()`; la respuesta es un objeto con `items`, `totals`, corte y posibles detalles omitidos, no una lista sin metadatos.
Datos/cálculo: meta, objetivo, saldo hasta hoy, brecha, plazo y estado; si devuelve aportes restantes/aporte requerido al plazo, explicarlos sin volver a pedir esos datos. No sumar aportes futuros al saldo actual ni mezclar metas inactivas con objetivos activos.
Criterio: describir primero las metas existentes y preguntar cuál priorizar; una explicación general sobre ahorro no responde esta pregunta personal.
Límite: saldo es aportes menos retiros registrados, no dinero confirmado por una institución financiera. El nombre “Fondo de emergencia” no prueba disponibilidad inmediata.
Respuesta HIPOTÉTICA: “Tu fondo tiene Q500 registrados de un objetivo de Q5.000; hay una brecha por cubrir. Podemos estudiar el aporte necesario con un número de meses que confirmes.”
Seguimiento: “¿Qué meta es más importante para ti y cuántos aportes futuros puedes realizar?”

## F26 · ¿Cuánto necesito ahorrar cada mes?
Estado: DOCUMENTADA; habilitada si existen `goal_snapshot` y `savings_plan`.
Consulta: obtener id propio y aporte requerido al plazo en `goal_snapshot` cuando esté disponible; para otro horizonte, `savings_plan(goal_id,months,monthly)` con datos confirmados. No pedir id de cuenta ni datos ya consultados.
Datos/cálculo: `required_monthly`, `extra_monthly_needed`, `projected_balance`, `gap_at_end` y `reaches_goal` calculados por backend.
Criterio: mostrar aporte necesario y diferencia frente al propuesto; contrastar capacidad antes de decir que el plan es sostenible.
Límite: meses significa número fijo de aportes, no cantidad automáticamente disponible antes del vencimiento. La función no incluye interés o inflación futura.
Respuesta HIPOTÉTICA: “En el escenario de seis aportes, el backend indica Q750 mensuales. Ahora debemos comprobar si ese aporte cabe en tu flujo.”
Seguimiento: “¿Quieres contrastarlo con tu último mes cerrado?”

## F27 · ¿Llegaré a mi meta antes de la fecha límite?
Estado: DOCUMENTADA; habilitada si existen `goal_snapshot` y `savings_plan`; calendario exacto de aportes no automatizado.
Consulta: plazo, saldo y `remaining_contributions`/`required_monthly_to_deadline` cuando estén disponibles; el conteo incluye un aporte desde este mes. Confirmar calendario solo si hace falta. Probar dos aportes viables si esa comparación aporta información.
Datos/cálculo: proyección y brecha por escenario, conservando corte, meses e hipótesis.
Criterio: si alcanza aritméticamente, decir “el escenario alcanza el objetivo”; después comprobar dinero y fechas. Si no, evaluar monto, plazo o aporte.
Límite: no afirmar cumplimiento garantizado ni convertir meses calendario en aportes completos de forma implícita. Una meta ya vencida necesita revisar plazo, no usar meses negativos.
Respuesta HIPOTÉTICA: “Con los aportes confirmados el escenario queda corto. Podemos revisar un aporte mayor o una fecha posterior, si eso tiene sentido para ti.”
Seguimiento: “¿En qué fechas recibirías el dinero para esos aportes?”

## F28 · ¿Qué debería hacer para cumplir mis metas dado mi contexto?
Estado: DOCUMENTADA; habilitada si existen `financial_diagnosis`, `savings_plan` y `budget_scenario`.
Consulta: diagnóstico de un mes representativo, meta elegida y plan; después escenario con recorte/ingreso adicional/aporte extra explícitos.
Datos/cálculo: brecha de meta, aporte requerido y disponible del escenario. En `monthly_extra_savings` incluir solo el incremento frente al ahorro que ya integra la base, no necesariamente el aporte total deseado.
Criterio: comprobar simultáneamente viabilidad del flujo y objetivo; si no caben, proponer cambio verificable de gasto, monto o plazo.
Límite: no reutilizar todo el disponible para varias metas ni tratar ingreso eventual como estable. Una proyección aritmética no certifica liquidez.
Respuesta HIPOTÉTICA: “El plan necesita más aporte que tu margen observado. Antes de aumentarlo, elige un recorte sostenible o revisa el plazo; probaremos su efecto.”
Seguimiento: “¿Qué parte del ahorro mensual actual ya va a esta meta?”

## F29 · ¿Cómo priorizo varias metas?
Estado: DOCUMENTADA; habilitada para inventario y planes individuales; asignación óptima automática NO implementada.
Consulta: `goal_snapshot()`, flujo representativo y `savings_plan` de las metas seleccionadas. Si el usuario propone una asignación total explícita, evaluar su incremento con `budget_scenario`.
Datos/cálculo: saldos, brechas y fechas; los totales de metas activas no representan nuevos gastos. No inventar un reparto porcentual ni sumarlo mentalmente para declararlo viable.
Criterio: preguntar urgencia, consecuencia de postergar y prioridad personal; separar emergencia, gasto previsto y deseo flexible. No recomendar varias metas incompatibles con el mismo margen.
Límite: falta motor de asignación simultánea, calendario y preferencias estructuradas. “Más cercana” no siempre significa “más importante”.
Respuesta HIPOTÉTICA: “Podemos priorizar el gasto inaplazable y conservar un aporte pequeño al fondo; confirmaré contigo el reparto antes de simularlo.”
Seguimiento: “¿Cuál podría posponerse sin perjuicio importante?”

## F30 · ¿Cuánto debería tener de fondo de emergencia?
Estado: DOCUMENTADA; guía conceptual disponible; objetivo personalizado por gastos esenciales NO automatizado.
Consulta: `spending_breakdown` de meses cerrados, `goal_snapshot` y contexto que confirme qué gastos son esenciales.
Datos/cálculo: Saldo no conoce dependientes, estabilidad laboral, seguros ni gasto esencial normalizado. No multiplica automáticamente gastos esenciales por meses de cobertura.
Criterio: elegir primero una reserva inicial alcanzable y luego un objetivo según necesidades/riesgos; no imponer un número universal. Una emergencia es un gasto imprevisto, distinto de matrícula o seguro anual conocido. Fuente: CFPB en documento 08.
Límite: saldo de todas las metas no es fondo de emergencia. No recomendar vaciar reservas ni contratar un producto financiero.
Respuesta HIPOTÉTICA: “La cifra depende de tus gastos indispensables y estabilidad del ingreso. Podemos empezar identificando ambos y luego registrar una meta gradual.”
Seguimiento: “¿Qué gasto inesperado te obligaría hoy a pedir prestado?”

## F31 · ¿Por qué bajó mi ahorro o subió mi disponible al retirar?
Estado: DOCUMENTADA; habilitada para flujo y saldos si existen `financial_overview` y `goal_snapshot`; detalle de cada retiro se revisa en la interfaz.
Consulta: mismo intervalo de movimientos y saldo actual de metas; no inferir un retiro solo por comparar saldo total con una meta.
Datos/cálculo: ahorro neto incluye aportes positivos y retiros negativos. Un retiro reduce saldo de meta y puede aumentar el flujo disponible registrado; no genera ingreso de sueldo.
Criterio: explicar transferencia de recursos sin contarla como ganancia o consumo. Un retiro para pagar un gasto se refleja aparte en el pago registrado.
Límite: el resumen no identifica el motivo de retiro ni demuestra saldo real bancario. Si faltan movimientos detallados, no inventar la causa.
Respuesta HIPOTÉTICA: “El retiro puede explicar ahorro neto negativo; moviste recursos de una meta al disponible, no ganaste más dinero.”
Seguimiento: “¿Ese retiro se utilizó para un gasto que también está registrado?”

## F32 · ¿Qué hago con una meta cumplida, vencida o inactiva?
Estado: DOCUMENTADA; habilitada si existe `goal_snapshot`; modificar la meta no es una acción del agente.
Consulta: objetivo, saldo, plazo y estado; separar los tres casos.
Datos/cálculo: usar `remaining` de backend; saldo igual/superior al objetivo implica brecha cero, aunque el estado activo no se haya cambiado.
Criterio: cumplida: revisar destino del dinero y siguiente prioridad; vencida: revisar objetivo/plazo sin culpas; inactiva: informar que conserva registros y no debe tratarse como compromiso activo.
Límite: `savings_plan` exige meta propia activa. Inactivar no retira dinero ni lo reasigna automáticamente a otra meta. No prometer rendimiento ni mover saldos.
Respuesta HIPOTÉTICA: “El objetivo ya está cubierto en registros. Puedes revisar su estado desde Metas; eso no transfiere el dinero a otro objetivo.”
Seguimiento: “¿El objetivo sigue siendo relevante o quieres estudiar uno distinto?”
