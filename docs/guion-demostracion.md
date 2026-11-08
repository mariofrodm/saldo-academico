# Guion de demostración

La exposición corta acredita el recorrido; la auditoría completa está en
[aceptación final](aceptacion-final.md). Usar la instalación publicada para que
sus consultas puedan verse después en Power BI. Localhost y cloud tienen bases
independientes y sus cifras no se deben mezclar.

## Antes de empezar

1. Abrir la URL pública con tiempo suficiente para que Render y Neon despierten.
2. Confirmar `/api/health`: base `ok` y SHA de la versión entregada.
3. Revisar sesión, cuotas personales y compartidas, y acceso institucional a BI.
   No ejecutar auditorías con IA real simultáneamente.
4. Usar los mismos usuario, fechas y servicios en web, API y Power BI.
5. Preparar Postman con variables privadas. No mostrar ni exportar contraseñas.
6. Confirmar que PDF y PBIX corresponden al corte de entrega de `estado.md`.

Las consultas generativas pueden requerir varias rondas. Dar prioridad a las
pruebas con fuentes externas que exige el enunciado. Espaciar las llamadas y
respetar el tiempo que indique el servidor; no insistir con reintentos rápidos.

## 1. Acceso y finanzas

Entrar como usuario. Mostrar un mes cerrado con registros y explicar la
separación de planificado, ejecutado y pendiente. Mostrar una meta con su
acordeón de movimientos y una plantilla recurrente. No modificar importes del
escenario de referencia durante la comparación.

Si se demuestra creación/edición, usar una cuenta de aceptación independiente
y anotar el cambio. Mostrar luego al administrador y la restricción de sus
funciones para el usuario normal.

## 2. Consulta tus finanzas: RAG y memoria

En una conversación nueva:

> ¿En qué gasté más en octubre de 2026?

Seguimiento en el mismo chat:

> En ese mismo mes, ¿pagué más en alimentación o en universidad?

> ¿Cuánto de diferencia?

Debe conservar período y categorías. En el escenario local original, Alimentación
Q1.000 frente a Universidad Q900 y diferencia Q100; validar las cifras cloud
antes de utilizarlas como respuesta esperada.

Para demostrar insuficiencia:

> ¿Cuál es la tasa exacta de mi préstamo personal y cuándo terminaré de pagarlo?

Debe reconocer los datos contractuales que no se registran. Abrir Historial y
mostrar documentos recuperados, herramientas y consumo. Las comparaciones
resueltas sin inferencia tienen cero llamadas; esto es una optimización, no una
omisión del historial.

## 3. Analiza tu presupuesto: fuente externa y varios pasos

> Consulta mis ingresos, pagos y ahorro de octubre de 2026. Consulta la inflación
> anual de Guatemala de 2025 en Banco Mundial y explica qué se puede comparar y
> qué no.

Mostrar en Historial el flujo consultado, la herramienta `inflation`, su fuente,
año y resultado. Un dato anual no debe presentarse como inflación de octubre.
Si la fuente está caída o no publica el período, señalar la ausencia; la prueba
de integración completa requiere un resultado externo válido documentado.

Opcional, si queda presupuesto:

> ¿Qué tan sano ves mi presupuesto de octubre de 2026? Dame dos prioridades.

## 4. Explora tus metas: herramienta externa y escenarios

Primero comprobar que existe una meta llamada Fondo de emergencia. Después:

> Consulta el Fondo de emergencia y su saldo actual. Consulta la referencia
> USD/GTQ de Banguat. Compara seis meses aportando Q500 mensuales con seis meses
> aportando Q750. Explica brevemente ambos resultados y qué significa esa
> referencia cambiaria.

Mostrar lectura de meta, tipo de cambio con fecha y dos simulaciones. Comprobar
que el saldo de la tarjeta no cambió: los escenarios no son aportes registrados.
El saldo inicial procede del entorno donde se ejecutó la consulta.

## 5. Historial y consumo

Mostrar una pregunta, sus pasos y todas las llamadas. Explicar:

- Una solicitud es una pregunta; puede incluir varias llamadas.
- Entrada más salida produce tokens totales.
- Fallos con consumo siguen registrados.
- La cuota personal acumulada no es el total del filtro de este mes.

## 6. Cliente externo

Importar `docs/postman.json`, iniciar sesión, consultar identidad, manifiesto
advisor y una herramienta de lectura. Esa consulta no consume Groq. Mostrar
historial y reportes. Si hace falta demostrar inferencia externa, ejecutar una
sola petición IA representativa y contabilizarla; no repetir toda la exposición.
El logout revoca el token: volver a usarlo debe devolver 401.

## 7. Power BI y archivos

1. Terminar las llamadas y esperar a que no queden solicitudes en curso.
2. Obtener summary y todas las páginas usage con un mismo `as_of`.
3. Actualizar el modelo semántico de Power BI; esperar estado completado.
4. Refrescar la vista y comparar cinco métricas con la web/API bajo el mismo
   conjunto: solicitudes, llamadas, entrada, salida y total.
5. Probar filtro de servicio, fechas con registros y un intervalo vacío.
6. Mostrar PBIX completo descargado, PDF, Swagger y repositorio/CI.

La actualización web no cambia un PBIX previamente descargado. El PDF y el PBIX
son archivos fechados; las cifras verificadas y fechas están en `estado.md`.

## Si una dependencia no responde

Conservar el error y no activar pagos. Explicar su causa con el historial y el
estado de cuotas. Puede mostrarse evidencia anterior claramente fechada como
respaldo, sin presentarla como ejecución en vivo. Las funciones financieras y
herramientas de lectura permiten seguir explicando el producto sin otra llamada
a Groq, según el servicio y las cuotas de acceso aplicables.
