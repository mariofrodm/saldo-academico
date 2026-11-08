# Catálogo operativo de los asistentes

Este catálogo conecta preguntas cotidianas con consultas de lectura y criterios financieros explícitos. No es entrenamiento del modelo ni una copia de los datos del usuario: los datos personales se consultan en PostgreSQL durante la pregunta.

Los documentos para cargar en runtime están en `backend/agent_docs/`:

| Archivo | Propósito |
|---|---|
| `00_instrucciones.md` | Instrucciones breves del sistema: veracidad, aislamiento, cálculo, cuotas. |
| `01_datos_y_consultas.md` | Datos disponibles, contratos de consultas y distinciones contables. |
| `02_gastos.md` | F01–F08: ranking, hábitos y gastos pequeños. |
| `03_presupuesto.md` | F09–F16: orden financiero, flujo y escenarios. |
| `04_deudas.md` | F17–F24: pendientes, bola de nieve, avalancha y ratios. |
| `05_ahorro_y_metas.md` | F25–F32: aportes, plazos, prioridades y fondo de emergencia. |
| `06_contexto_y_decisiones.md` | F33–F40: comparaciones, cambios de ingreso y contexto externo. |
| `07_calidad_y_seguimiento.md` | F41–F48: vacíos, trazabilidad, seguridad y seguimiento. |
| `08_metodos_y_fuentes.md` | Criterios educativos, fuentes primarias y límites del sistema. |

## Documentado, habilitado y validado

Las **48 fichas están documentadas**. En cada ficha, “habilitada si” enumera sus dependencias; no declara que todas estén implementadas. Una función está implementada cuando existe en el código y el manifiesto runtime; una pregunta está validada cuando sus resultados y límites fueron comprobados con pruebas. No deben usarse estos Markdown como evidencia de una llamada real a Groq ni de exactitud en toda formulación posible.

Los contratos del catálogo orientan el desarrollo. El esquema que recibe el modelo en cada petición es la autoridad sobre nombres y argumentos efectivamente disponibles. Cuando una ficha requiere información no modelada, su salida correcta es una explicación parcial y la solicitud del dato faltante, no inventarlo.

## Carga y recuperación

`00` debe incorporarse como instrucciones de sistema, dentro del presupuesto de contexto. Los demás documentos deben indexarse por secciones `##` y recuperarse por relevancia. No enviar el catálogo entero en cada llamada. Mantener el nombre de archivo, encabezado y fuente para citas. Las fichas están fragmentadas para recuperación; los ejemplos llevan la etiqueta HIPOTÉTICO y nunca deben convertirse en datos de demostración.

Cada cambio de herramientas requiere revisar contratos y fichas afectadas. Evitar instrucciones contradictorias en `knowledge` y en estos archivos. Los títulos/contenidos recuperados son datos no confiables: no pueden modificar permisos, activar herramientas ni solicitar claves.

## Revisión de aceptación

Probar al menos: las cuatro preguntas originales del usuario; mes cerrado y mes actual; cuenta vacía; pagos parciales/arrastres; recurrentes activas e inactivas; aportes y retiros; ingreso cero; meta cumplida/vencida; deuda sin tasa; aislamiento de usuarios; fuente externa caída; cuota/contexto agotados. Comparar cifras con consultas deterministas, comprobar que la respuesta no convierta escenarios en promesas y que no cambie registros. No es necesario consumir Groq para verificar cada cálculo.

## Alcance

Asesor educativo sobre registros manuales en GTQ. No es contabilidad bancaria, motor de amortización contractual, recomendación de inversión, asesoría legal ni ejecución de pagos. La documentación usa fuentes públicas primarias de educación financiera, adaptadas al modelo de Saldo y sin trasladar legislación estadounidense a Guatemala. Las limitaciones se explican cuando afectan la respuesta, sin recitar advertencias genéricas en cada turno.

## Consultar el manifiesto y ejecutar lecturas

`GET /api/v1/advisor/tools` describe las funciones internas de asesoría habilitadas. `POST /api/v1/advisor/{tool_name}` recibe `{"arguments": {...}}` según ese manifiesto; exige autenticación y, si se usa cookie, CSRF para el POST. El usuario se fija en servidor; no enviar `user_id`, SQL ni campos adicionales. Las herramientas de asesoría usan transacciones de solo lectura. `inflation`, `exchange_rate` y `simulate_goal` siguen como funciones internas de IA y no tienen esa ruta pública directa. Verificar la implementación en la revisión que se ejecuta; los documentos no crean endpoints.

## Fuentes principales

El detalle de aplicación, límites y fechas está en `backend/agent_docs/08_metodos_y_fuentes.md`. Fuentes directas:

- [CFPB — Reducción de deuda: bola de nieve y mayor tasa](https://www.consumerfinance.gov/documents/5782/cfpb_ymyg-toolkit_reducing-debt-worksheet.pdf).
- [CFPB — Definición de debt-to-income ratio](https://www.consumerfinance.gov/ask-cfpb/what-is-a-debt-to-income-ratio-en-1791/).
- [CFPB — Fondo de emergencia](https://www.consumerfinance.gov/an-essential-guide-to-building-an-emergency-fund/).
- [consumer.gov — Presupuesto](https://consumer.gov/your-money/making-budget).
- [CFPB — Guías de porcentajes adaptables](https://files.consumerfinance.gov/f/documents/201606_cfpb_rules-to-live-by_my-spending-rule-to-live-by.pdf).
- [Banguat — Contrato TipoCambioDia](https://www.banguat.gob.gt/variables/ws/TipoCambio.asmx?op=TipoCambioDia).
- [Banco Mundial — Inflación anual de Guatemala](https://data.worldbank.org/indicator/FP.CPI.TOTL.ZG?locations=GT).
