# Especificación académica acotada — 2 de noviembre de 2026

## Objetivo y usuarios

Ayudar a estudiantes y personas que registran manualmente sus finanzas a comparar
presupuesto y ejecución y explorar metas con asistencia explicable de IA.
Usuario: administra sus propios datos e historial. Administrador: gestiona usuarios,
corpus y servicios, asigna cuotas y consulta consumo global. Una credencial BI
independiente solo permite consultar reportes; no puede ejecutar IA ni CRUD.

## Funciones incluidas

- Categorías por usuario; ingresos/egresos GTQ planificados y pagos parciales.
- Plantillas recurrentes mensuales simples. Instancias únicas por plantilla/período;
  las ediciones de plantilla afectan meses todavía no generados. Generación
  al solicitar el tablero, sin cron pagado. Pendientes anteriores son la misma
  obligación, no duplicados nuevos.
- Metas de ahorro GTQ con aportes y retiros manuales; saldo derivado de movimientos.
  Un aporte reduce disponible y aumenta ahorro; no se interpreta como gasto de
  consumo. Simulaciones USD usan referencia externa, no sustituyen tasas reales.
- Tres servicios accesibles por GUI y API, historial persistido y reporte de uso.
- Administración, Swagger, Postman, PostgreSQL, pruebas y despliegue condicionado.

## Tres servicios de IA

1. `rag`: recupera fragmentos del corpus administrado y movimientos autorizados
   de PostgreSQL; fuentes identificables, memoria por conversación y declaración
   de insuficiencia. Nunca entrega datos de otro usuario.
2. `budget`: agente que elige consultas de ingresos/egresos por período e indicadores
   externos de inflación de Guatemala (Banco Mundial), compara y explica resultados.
   Indicadores anuales no se presentan como datos mensuales o predicciones.
3. `goals`: agente que consulta metas/compromisos, obtiene referencia USD/GTQ de
   Banguat y ejecuta simulaciones con aportes/plazos distintos. Sin compras, créditos,
   inversiones o modificaciones automáticas de los registros financieros.

En los agentes se registran herramientas y resultados intermedios. Un texto único
precalculado o tres etiquetas del mismo chatbot no satisfacen el alcance. Fuentes
externas consultadas desde backend, con límites, validación TLS, fecha y procedencia.
Si una fuente falla se informa: no se inventan datos ni se sustituye por valores
ficticios sin identificar. Cálculos en Decimal, no en el modelo de lenguaje.

## Reglas de datos

- Importes NUMERIC(15,2), redondeo HALF_UP; tasas NUMERIC(12,6). API devuelve
  importes como cadenas decimales. No usar float para operaciones monetarias.
- Pagos separados de obligaciones: se conservan fecha y monto de cada ejecución.
- Dinero disponible = ingresos ejecutados − egresos ejecutados − aportes netos
  a ahorro. El balance consolidado no considera el ahorro como gasto de consumo.
- No usar DTI ni umbrales de salud financiera universales en esta versión.
- Fechas operativas America/Guatemala; auditoría y solicitudes IA en UTC.
- Historial preservado; anulación/inactivación para entidades con movimientos.
- Cuotas verificadas y reservadas atómicamente antes de cada llamada al proveedor;
  registrar todas las rondas, incluyendo errores y uso desconocido conservador.
- Misma API de consumo para reporte web y Power BI; solicitudes ≠ llamadas IA.

## Fuera de esta entrega

Tarjetas/FIFO, intereses, Visacuotas, extrafinanciamientos, amortización bancaria,
fondos compartidos, multidivisa operativa general, automatismos sobre históricos,
integración bancaria, pagos reales y asesoría de inversiones.

## Entregables y condiciones

Código/pruebas/CI, SQL y seed ficticio, Swagger/Postman, app/API HTTPS,
PDF de propuesta/arquitectura/modelo/evidencias y PBIX completo conectado a API.
Reporte obligatorio: consultas y tokens por usuario/fecha/servicio, coincidente
con web; no se reemplaza con gráficos de ingresos y gastos.

Ubuntu para desarrollo, Docker y administración. Power BI web como primera vía;
Windows ya licenciado solo si se necesita Desktop. Costo permitido USD 0.
Neon Free, Render Free y Groq Free; sin tarjetas, upgrades, cron pagado o embeddings
facturables. Aplicación independiente del vencimiento de Fabric.
