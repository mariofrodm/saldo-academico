# Estado verificable - 8 de noviembre de 2026

El cierre corresponde al enunciado original y se comprueba con la
[matriz de 15 criterios](cumplimiento.md). Los datos de localhost y de la nube
son distintos; el escenario local ampliado no se presenta como sincronizado.
Los 15 criterios de la matriz están comprobados en el alcance indicado. La
implementación y los archivos fechados se distinguen de las operaciones
adicionales pendientes y de cualquier disponibilidad futura de proveedores.

## Implementación y despliegue

La aplicación ofrece autenticación, registro, roles admin/user/BI, CRUD de
usuarios y configuraciones de los tres servicios, categorías, obligaciones,
pagos parciales, arrastres, recurrentes y metas con aportes/retiros. Incluye
historial, consumo, API REST, Swagger, cliente externo y reporte Power BI.
Las metas despliegan movimientos por tarjeta y su eliminación confirmada es
transaccional y auditada. La edición del inicio de recurrentes se conserva sin
reescribir instancias anteriores.

React/TypeScript/Vite y FastAPI/Python se sirven desde un contenedor en Render
Free. PostgreSQL 18 en Neon Free conserva el estado; Docker local/CI utiliza
PostgreSQL 17. Migraciones Alembic, corpus, configuración y preparación de datos
son operaciones distintas de publicar código. No hay pagos ni banca real.

La implementación funcional acreditada es
`bb4dc3293d90307dc6afce6be729e022b40fb0f8`, con
[CI 42499168192](https://github.com/mariofrodm/saldo-academico/actions/runs/42499168192)
exitoso en backend, contenedor y deploy. Render confirmó ese SHA y base `ok`.
Las publicaciones anteriores a7416a4, 02c78a8 y dc625e2 quedan como trazabilidad.
Un commit posterior que publique solo documentación/artefactos puede cambiar el
SHA servido manteniendo esta implementación funcional; no se reetiquetan los
ensayos reales históricos como si se hubieran ejecutado de nuevo.

## Pruebas y agentes

- Aceptación API local final: **63 comprobaciones**, cero llamadas Groq.
- Aceptación cloud de lectura: **65 comprobaciones**, cero llamadas Groq,
  correspondiente al SHA `a7416a4`, sin mutaciones financieras ni de configuración.
- Clon limpio: **45 comprobaciones y cuatro chats calculados** sin proveedor.
- Frontend: **14 pruebas** y compilación aprobadas; filtros de fecha/servicio
  comprobados en navegador, incluyendo un intervalo vacío.
- La nueva guarda se comprobó con **59 pruebas y cinco subpruebas dirigidas**,
  usando también el candidato real archivado sin otra inferencia. No sumar
  esas pruebas parciales a la suite completa como casos adicionales.
- CI final: **417 pruebas backend, 106 subpruebas**, una advertencia de
  deprecación no bloqueante, 65,82 segundos. Es la ejecución completa; las
  pruebas dirigidas forman parte de la suite y no se suman otra vez.
- Congelación final cloud: **31 comprobaciones**, cero llamadas IA, health del
  SHA final y las mismas nueve solicitudes que se importaron en Power BI.

Pruebas reales conservadas en historial:

| Servicio / entorno | Llamadas | Tokens | Resultado y límite observado |
|---|---:|---:|---|
| RAG cloud | 1 | 2.256 | Respuesta natural con fuentes/lecturas propias; no se asumieron finanzas inexistentes. |
| Presupuesto cloud, repetición | 2 | 1.731 | Flujo e inflación anual reales y aritmética correctos. Se detectó una frase que presentaba el margen como capacidad disponible; la guarda final se validó contra ese texto sin gastar más IA. |
| Metas cloud, ensayo anterior | 2 | 2.186 | Saldo Q500, proyecciones Q3.500/Q5.000 y Banguat correctos. La afirmación de plazo se corrigió en las instrucciones; el intento permanece contabilizado. |
| Metas local, instrucciones finales | 2 | 2.693 | Saldo Q550 y proyecciones Q3.550/Q5.050, sin prometer el calendario de aportes ni asequibilidad. |

Los agentes externos utilizan herramientas compuestas elegidas por el modelo:
lecturas/cálculos/fuente externa secuenciales entre una inferencia de selección
y otra de explicación. El recorrido general usa la guía `00`; esos dos flujos
usan `external_system` específico y compacto. La guarda de cifras y la barrera
sobre capacidad reducen errores concretos; no certifican toda interpretación
semántica ni convierten al modelo en asesor infalible.

## Reporte y Power BI actualizados

La actualización del modelo terminó el **8/11/2026 a las 04:58:22 Guatemala**.
Web, API y Power BI coinciden para noviembre, usuario 2 y el mismo conjunto
terminado. La congelación API final tiene corte
**2026-11-08T16:21:20.915006+00:00**:

| Servicio | Solicitudes | Llamadas | Entrada | Salida | Total |
|---|---:|---:|---:|---:|---:|
| Presupuesto | 4 | 10 | 5.557 | 1.449 | 7.006 |
| Metas | 3 | 10 | 6.610 | 1.040 | 7.650 |
| Consulta tus finanzas | 2 | 2 | 2.698 | 141 | 2.839 |
| **Total** | **9** | **22** | **14.865** | **2.630** | **17.495** |

El refresco BI es anterior al último corte API: se verificaron los mismos nueve
IDs y métricas, sin nuevas solicitudes entre ambos cortes. Cada importación
conserva su propio `as_of`; no se afirma que sean el mismo instante. Se
comprobaron filtros de servicio, fecha y período vacío. La importación usa
la API HTTPS, cuenta BI de lectura, paginación y un `as_of` estable, sin gateway
local ni contraseña en M. La actualización programada está desactivada.

El PBIX completo en `powerbi/Saldo_Consultas_y_Consumo.pbix` se descargó desde
Ubuntu el 8/11 y su validación contra la congelación final encontró el
modelo importado, la consulta API paginada y los mismos nueve IDs y métricas,
sin filas adicionales/faltantes. Tamaño **793.621 bytes**, SHA256
`8a213741d3065afd3dfd2d66e2f3b5d5396f2f1ced8ef0e8f9a0a8c5d7d33e9c`.
El análisis revisó ZIP, modelo ABF y 232 streams sin coincidencias con los
secretos operativos conocidos. Es una comprobación con parser de terceros,
no certificación de Microsoft; Power BI Desktop en Windows no se ejecutó.

Power BI, PDF y PBIX son cortes fechados. Un archivo ya descargado no cambia
al ejecutar otra pregunta ni al refrescar solo la vista del informe.

## Datos, recuperación y costo cero

Cloud conserva la semilla: tres categorías, tres obligaciones, tres pagos y
Fondo de emergencia Q500. Noviembre registra Q6.000 de ingresos, Q1.400 de pagos,
Q500 de ahorro y Q4.100 de flujo. Local contiene el escenario ampliado y las
ediciones legítimas del usuario; sus cifras no deben compararse con Power BI.

La copia ampliada a Neon sigue pendiente de confirmación específica después
de un rechazo de revisión automática. El plan/respaldo está preparado; no se
aplicó esa escritura ni se modificaron cuotas para habilitarla. Esta operación
adicional se distingue del cumplimiento original sobre la semilla publicada.

El respaldo cloud original se restauró en PostgreSQL 18 en un contenedor
separado: revisión de origen `0003`, base original conservada. El SQL y las
migraciones posteriores se comprobaron en arranque limpio. Esa evidencia no se
presenta como restauración de una futura base sincronizada distinta.

Al corte de ensayos, Ana local conserva **65.705/100.000** tokens acumulados y
cero reservas; presupuesto diario local **97.725/100.000**, quedan **2.275**.
Ana cloud conserva **17.495/20.000**. No se aumentaron ni reiniciaron cuotas.
Preparar la exposición después de revisar márgenes; el día UTC de la app
renueva a las 18:00 Guatemala y la cuota personal no se renueva automáticamente.

Render, Neon y Groq permanecen en Free, sin añadir tarjetas ni servicios de
pago. Tienen cuotas y suspensiones por inactividad; despertar antes de la demo
sin pings artificiales. Microsoft mostraba 11 días de prueba en la inspección;
revisar vigencia. La clave Groq configurada vence el 2/12/2026. Credenciales,
hooks, claves y respaldos privados quedan fuera de Git; retirarlos al terminar.

El escaneo de 117 archivos públicos comparó 42 patrones/valores privados sin
coincidencias; PBIX y PDF se revisan también como archivos estructurados. El
escaneo es una comprobación acotada, no una auditoría de seguridad completa.

## Archivos finales y operación pendiente adicional

El PDF final `output/pdf/Informe_Saldo_Academico.pdf` tiene **12 páginas**,
408.831 bytes y SHA256
`7be16e64dc648585b93047e87c3471617ac9878bb17a143f18922af8e0b8f4ed`.
Se renderizaron e inspeccionaron todas: diagramas, tablas, capturas, pies y
secciones legibles, sin recortes, solapamientos ni página huérfana. El escaneo
revisó texto, metadatos, anotaciones, 53 objetos y 22 streams descomprimidos contra
25 valores privados conocidos y patrones de credenciales, sin coincidencias.
Ese escaneo no reemplaza una auditoría exhaustiva de seguridad.

PDF, PBIX, README, SQL, migraciones, colección Postman y guion corresponden al
cierre documentado. Los manifest y evidencias privadas conservan las fechas y
orígenes; no incluyen claves en los artefactos públicos.

La única operación adicional de escenario pendiente es la copia ampliada de Ana
a Neon, sujeta a confirmación específica. La semilla publicada sigue siendo la
base de la demostración cloud. No se da por aplicada ni se necesitan pagos para
mantener esa distinción.

La explicación sencilla completa está en [cómo funciona](como-funciona.md) y
el recorrido para presentar en [guion de demostración](guion-demostracion.md).
