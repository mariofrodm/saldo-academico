# Preguntas para ordenar las finanzas

## F09 · ¿Qué puedo hacer para ordenar mis finanzas?
Estado: DOCUMENTADA; habilitada si existe `financial_diagnosis` o las consultas equivalentes por separado.
Consulta: `financial_diagnosis(start,end,as_of)` para flujo, categorías, recurrentes, pendientes de Deudas y metas; tomar un mes cerrado representativo y corte actual.
Datos/cálculo: usar totales completos y advertir detalle omitido; distinguir déficit, vencidos y metas sin aporte viable.
Criterio: proponer hasta tres pasos según datos: completar registros, ordenar vencimientos y elegir un cambio de gasto/aporte medible. Priorizar estabilidad antes de acelerar todas las metas.
Límite: disponible registrado no es dinero bancario libre; faltan saldo inicial y gastos no cargados.
Respuesta HIPOTÉTICA: “Primero confirma los pagos pendientes; después fija un límite a una categoría flexible y prueba el aporte a la meta. Revisaremos el resultado en el próximo cierre.”
Seguimiento: “¿Los ingresos y gastos de ese mes están completos?”

## F10 · ¿Cuánto dinero me queda disponible?
Estado: DOCUMENTADA; habilitada si existe `financial_overview`.
Consulta: `financial_overview(start,end)`; mes actual hasta hoy salvo período pedido.
Datos/cálculo: leer `current.available`, calculado como ingreso − egreso − ahorro neto. Mostrar las tres partidas; no recalcular desde una lista truncada.
Criterio: llamarlo “flujo disponible registrado en el período”. Si se pregunta por efectivo hoy, aclarar que falta saldo inicial de caja/cuentas y operaciones omitidas.
Límite: no restar dos veces ahorro ya incluido; un retiro no es ingreso nuevo. No asumir que disponible positivo puede asignarse entero sin revisar vencimientos.
Respuesta HIPOTÉTICA: “El flujo registrado deja Q650 después de pagos y ahorro neto. No equivale al saldo de tu cuenta; antes de asignarlo revisaría los vencimientos próximos.”
Seguimiento: “¿Quieres revisar compromisos pendientes antes de decidir el destino?”

## F11 · ¿Mi presupuesto está en déficit?
Estado: DOCUMENTADA; habilitada si existe `financial_overview`.
Consulta: flujo del último mes cerrado y, separadamente, del actual hasta hoy.
Datos/cálculo: `income`, `expense`, `net_savings`, `available`; ratios si el backend los devuelve y el ingreso no es cero.
Criterio: disponible negativo puede reflejar más pagos o aportes de ahorro que ingresos registrados; separar consumo de ahorro y retiros. Revisar completitud y pagos excepcionales antes de concluir desequilibrio permanente.
Límite: un mes con sueldo aún no cobrado no describe capacidad mensual estable. Sin saldo inicial no se demuestra descubierto bancario.
Respuesta HIPOTÉTICA: “El flujo registrado es negativo; parte corresponde al aporte de ahorro. Revisemos si ese aporte era sostenible y si falta registrar un ingreso.”
Seguimiento: “¿Hubo ingresos pendientes o una compra que no se repetirá?”

## F12 · ¿Qué límite de gasto puedo ponerme?
Estado: DOCUMENTADA; cobertura parcial: `spending_breakdown` y `budget_scenario` prueban importes; no existe motor de sobres semanales.
Consulta: mes cerrado, identificar categoría flexible y simular un recorte mensual concreto acordado con el usuario.
Datos/cálculo: comparar disponible base y `scenario_available`; mostrar hipótesis. El backend no convierte automáticamente el límite mensual a semanas o días.
Criterio: escoger un cambio practicable y revisarlo tras un cierre; un límite es una decisión, no una obligación inferida de un porcentaje universal.
Límite: no presentar una división semanal calculada por el modelo ni crear límites en la aplicación si no existe esa funcionalidad.
Respuesta HIPOTÉTICA: “Podemos ensayar Q150 menos al mes en una categoría que tú elijas y comprobar el flujo resultante; sería una pauta para seguimiento.”
Seguimiento: “¿Qué monto y categoría considerarías realistas?”

## F13 · ¿Cómo me organizo si mis ingresos varían?
Estado: DOCUMENTADA; habilitada para descripción si existe `financial_overview`; promedio y percentiles no implementados por este contrato.
Consulta: tres meses cerrados por separado; mostrar ingreso, egreso y disponible de cada uno. No llamar “salario garantizado” al máximo observado.
Datos/cálculo: importes devueltos por cada consulta; no calcular un promedio nuevo sin backend que lo produzca.
Criterio: usar un mes prudente como base elegida explícitamente, distinguir ingresos estables de eventuales confirmados por el usuario y preparar un colchón para meses bajos.
Límite: tres meses no prueban estacionalidad, estabilidad laboral ni ingresos futuros. El sistema no etiqueta automáticamente cada ingreso como seguro.
Respuesta HIPOTÉTICA: “Los meses registrados son distintos; conviene comprometer aportes con una base conservadora, dejando el ingreso eventual para acelerar objetivos cuando se cobre.”
Seguimiento: “¿Cuál de esos ingresos es recurrente y cuál fue extraordinario?”

## F14 · ¿Cómo preparo un gasto grande que sé que vendrá?
Estado: DOCUMENTADA; habilitada si existen `goal_snapshot`, `savings_plan` y `budget_scenario`.
Consulta: si el gasto ya está como meta, usar su id y aportes futuros confirmados. Si no existe, explicar cómo registrarlo desde la interfaz; el agente no lo crea.
Datos/cálculo: monto objetivo, saldo, meses y aporte requerido del backend, contrastados contra un flujo mensual representativo.
Criterio: separar gastos previsibles de emergencias; reservarlos con tiempo y comprobar que no compitan dos planes por el mismo dinero.
Límite: no sumar una meta y una obligación del mismo gasto como dos necesidades financieras independientes. La simulación no incluye variación de precio futura.
Respuesta HIPOTÉTICA: “La matrícula prevista puede planificarse como meta. Tras confirmar monto y número de aportes, consulto cuánto requeriría mensualmente.”
Seguimiento: “¿Ya existe esa meta y cuándo debes pagar?”

## F15 · ¿Y si este mes no tuve ingresos?
Estado: DOCUMENTADA; habilitada si existen `financial_overview` y `obligations_snapshot`.
Consulta: flujo del período y vencimientos al corte.
Datos/cálculo: si ingreso es cero, ratios sobre ingreso son `null`/no calculables; mostrar importes absolutos. No convertirlos en 0 % o infinito ni diagnosticar insolvencia desde ellos.
Criterio: confirmar ingreso faltante, fechas de cobro, recursos disponibles fuera de Saldo y prioridades esenciales. Evitar nuevos aportes automáticos insostenibles.
Límite: no hay saldo bancario inicial ni patrimonio; no se demuestra ausencia total de recursos.
Respuesta HIPOTÉTICA: “No hay ingresos registrados en el intervalo, por eso no puedo expresar la carga como porcentaje. Revisemos si aún no cobraste y qué vence antes.”
Seguimiento: “¿No hubo ingreso o falta cargarlo?”

## F16 · ¿Por qué llego sin dinero antes de cobrar?
Estado: DOCUMENTADA; cobertura parcial: flujo por período y pendientes; no hay calendario de caja con saldo inicial.
Consulta: `financial_overview` por intervalos concretos y `obligations_snapshot(as_of)`; pedir próxima fecha de cobro y confirmar dinero inicial fuera del sistema.
Datos/cálculo: vencimientos y pagos registrados; no proyectar un saldo diario ni quincenal sin la base que falta.
Criterio: el orden de cobros/pagos puede generar tensión aun si el mes completo resulta positivo. Plantear al usuario revisar fechas y reservar lo esencial.
Límite: la existencia de un compromiso no prueba que el acreedor permita cambiar su fecha. No negociar ni ejecutar pagos desde el agente.
Respuesta HIPOTÉTICA: “Puede haber un desajuste de fechas; veo compromisos anteriores al cobro que indicas. Saldo no conoce tu caja inicial para certificar la brecha.”
Seguimiento: “¿Cuánto tienes reservado y qué fecha de cobro es segura?”
