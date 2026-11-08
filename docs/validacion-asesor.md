# Ampliación local del asesor — 2 de noviembre de 2026

La ampliación está activa en la instalación Ubuntu de `http://127.0.0.1:8000`.
Los datos, herramientas y guías de esta ampliación todavía no se publicaron
en Render/Neon. El PDF/PBIX entregado conserva su corte histórico anterior.

## Cuenta de demostración

Se amplió `demo@example.test` sin borrar registros ni historial de IA.
Contadores comprobados después de la carga:

- 15 categorías, 185 compromisos y 178 pagos.
- 8 plantillas recurrentes: 7 activas desde diciembre y 1 inactiva.
- 6 metas: en progreso, cumplida, vencida e inactiva; 12 movimientos de ahorro.
- 3 deudas identificadas: pendientes Q550, Q2.050 y Q5.300, total Q7.900.
- 48 fichas de preguntas y 79 fragmentos educativos indexados, además de la
  fuente educativa original. Nueve archivos Markdown versionados.

Los contadores incluyen el compromiso «Demo · Material de estudio» y su
abono Q50 de la demostración anterior. Se normalizaron únicamente cuatro
fechas de la semilla original; ver `escenario-demo.md`. Respaldo privado
anterior a la ampliación en `evidencias-locales/asesor-20261102/`.

## Verificación determinista

65 pruebas automatizadas aprobaron contra PostgreSQL temporal aislado.
Groq y fuentes externas se simulan en esas pruebas, sin consumir cuota.
Incluyen importación idempotente, agregaciones completas, pagos parciales,
fechas/cortes, ausencia de datos, escenarios, metas vencidas/cumplidas,
aislamiento y rechazo de escrituras en las herramientas. La compilación
TypeScript/Vite y el arranque saludable del contenedor también aprobaron.
Hay una advertencia de deprecación de Starlette/TestClient no bloqueante.

También se verificó la API autenticada con los datos cargados:

| Consulta | Resultado esperado y comprobado |
|---|---|
| Ranking octubre | Vivienda Q1.500; gasto total Q7.177, 13 categorías de egreso |
| Flujo octubre | Ingreso Q7.250, gasto Q7.177, ahorro neto Q0, disponible Q73 |
| Deudas al 2 de noviembre | Q7.900 pendientes; tres registros identificados |
| Ratio observable octubre | Pagos Deudas/ingreso registrado 10,34%; no DTI contractual |
| Pagos individuales hasta Q50, octubre | 60 pagos, Q1.234; candidatos, no ahorro garantizado |
| Metas actuales | 5 activas, 1 inactiva; una activa vencida sin financiar |
| Aportes necesarios a metas no vencidas | Q2.316,67 al mes bajo un aporte por mes desde noviembre |
| Escenario octubre | Reducir Q412,50, añadir Q200 a deuda y Q200 a ahorro deja Q85,50 |

Los Q2.316,67 expresan necesidad matemática, no capacidad económica ni
garantía. Contrastar contra flujo representativo, obligaciones y datos omitidos.

## Límites y mantenimiento

La importación de Markdown se ejecuta explícitamente con
`python -m backend.knowledge`. Las instrucciones base se leen por petición;
los demás documentos se recuperan por relevancia en los tres asistentes.
Nunca se envía el catálogo completo en cada llamada. El escenario específico
de Ana está fuera del corpus global para no contaminar otras cuentas.

`GET /api/v1/advisor/tools` y `POST /api/v1/advisor/{tool_name}` permiten
probar consultas sin Groq. El usuario se obtiene de la sesión/Bearer, jamás
de argumentos enviados por el modelo. Las herramientas usan transacciones
de solo lectura. Totales completos y detalles recortados se distinguen;
los resultados completos se guardan en el historial de herramientas de IA.

No hay tasas, mínimos contractuales, amortización, saldo bancario ni DTI
formal. Las fichas que los necesitan explican el límite. La cobertura
determinista no demuestra que toda formulación natural funcione: las
respuestas reales deben contrastarse con estos resultados y sus fuentes.
