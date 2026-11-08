# Recorrido de aceptación final

Actualizado el 8 de noviembre de 2026. Ejecutar en orden:
**local → publicación por CI/CD → nube → Power BI → entregables**.

Una respuesta HTTP 200 no prueba que la recomendación sea correcta. Cada
caso debe contrastarse con datos, herramientas y fuentes del historial.
Registrar `Aprobado`, `Falló` o `Pendiente`, con captura/JSON y descripción.
No dar por cerrada la etapa mientras haya un fallo obligatorio sin resolver.

## 0. Estado de partida y preparación

- Local: http://127.0.0.1:8000/; Swagger: http://127.0.0.1:8000/docs.
- Nube: https://saldo-academico.onrender.com; es una base distinta.
- Power BI actual consulta la nube. Las operaciones locales no aparecen allí.
- Ana: `demo@example.test`. Administrador: `admin@example.test`.
- Contraseñas locales: variables `DEMO_PASSWORD` y `ADMIN_PASSWORD` de `.env`.
  Las credenciales cloud son diferentes; no intercambiarlas ni publicarlas.
- Guardar un respaldo privado antes de pruebas de escritura; nunca usar la única
  base de presentación como laboratorio de borrado/restauración.
- Leer `/api/health`, `/me` y los reportes antes de empezar. Registrar SHA,
  revisión de migraciones, cuotas/reservas y alcance. No asumir contadores fijos.
- Usar `docs/estado.md` para consultar la última suite y publicación acreditadas.
  Las auditorías locales anteriores no sustituyen la aceptación cloud nueva.
- Ana tiene un máximo configurable acumulado de 100.000. No reiniciar usados
  ni cambiar de cuenta para eludir un límite. Revisar además el presupuesto
  compartido: aumenta la cuota personal solo cuando esa sea la causa real.
- La lectura `advisor` y los recorridos `local_only` no consumen Groq. Planificar
  pocas llamadas reales, preferentemente las que acreditan fuentes externas; no
  ejecutar ensayos masivos mientras se prepara una demostración.

Para repetir la verificación sin IA desde la raíz de `finanzas-ia`:

```sh
docker compose -p saldo_academico exec -T app python - < scripts/verificar_aceptacion.py
```

Termina con `"passed": true`; las credenciales y tokens no se imprimen.
Las referencias financieras que verifica corresponden al escenario conocido:
un fallo tras una edición manual exige revisar esa edición, no restaurar datos
o cambiar el esperado para ocultar la diferencia.

## 1. Acceso y referencia financiera de Ana

Las cifras de esta sección son la referencia del escenario ampliado local
antecedente a ediciones manuales. Antes del ensayo, obtener los valores actuales
de cada entorno y conservarlos como esperado de ese lote. No restaurar datos ni
eliminar cambios del usuario para que una captura coincida con esta tabla.
El 8/11 se observaron noviembre Q6.000/Q2.277/Q1.275/Q2.448 y computadora Q1.050;
la deuda al 8/11 bajó a Q7.350 tras pagar el préstamo familiar. Al 7/11 aún eran
Q7.900. La comparación de octubre no cambió. Ver `escenario-demo.md`.

1. Abrir la aplicación; confirmar el nombre de Ana y los seis módulos personales.
2. Cerrar sesión: debe aparecer el formulario y los datos deben quedar protegidos.
3. Volver a entrar. No debe aparecer Administración para el rol usuario.
4. En **01 Mis finanzas**, elegir cada mes con **Mes del tablero**. Esperar la
   carga; verificar que encabezado, selector y cantidades pertenecen al mismo mes.

| Mes | Ingresos ejecutados | Egresos ejecutados | Ahorro neto | Disponible |
|---|---:|---:|---:|---:|
| Septiembre 2026 | Q6.900 | Q6.297 | Q500 | Q103 |
| Octubre 2026 | Q7.250 | Q7.177 | Q0 | Q73 |
| Noviembre 2026, movimientos del escenario hasta el día 2 | Q6.000 | Q1.727 | Q625 | Q3.648 |

5. Recargar la página: los datos se conservan. Una sesión válida también se conserva.
6. En **02 Metas de ahorro**, comprobar las seis metas: fondo Q550/Q5.000,
   computadora Q400/Q4.500, diplomado Q150/Q1.800, curso Q25/Q25 cumplido,
   renovación Q0/Q600 con plazo vencido y viaje Q0/Q1.200 inactivo.
7. En **03 Recurrentes**, comprobar siete activas desde diciembre de 2026 y
   gimnasio inactivo. Son importes previstos: no representan pagos realizados.

Evidencia: capturas de las tarjetas de los meses, metas y recurrentes. No editar
estos registros de Ana durante el recorrido de referencia.

## 2. RAG y preguntas cotidianas

En **04 Asistentes IA → Consulta tus finanzas**. Iniciar **Nueva conversación**
entre temas; conservarla solamente para el seguimiento indicado. Espaciar las
solicitudes, esperar que la anterior termine y dejar aproximadamente un minuto
entre pruebas. Una solicitud puede consumir varias rondas. Si aparece 429,
registrar el mensaje para distinguir cuota personal de límite compartido o del
proveedor; no repetir rápidamente ni activar pagos. Un 413 o un límite de pasos
sin respuesta es un resultado fallido que debemos corregir o acotar antes del cierre.

| Caso | Pregunta para copiar | Resultado que debe verificarse |
|---|---|---|
| IA01 | ¿En qué gasté más en octubre de 2026? | Vivienda Q1.500; pagos reales del período, no principal de deuda ni previsiones. Fuente interna y consulta de datos. |
| IA02, mismo chat | En ese mismo mes, ¿pagué más en alimentación o en universidad? | Conserva octubre: alimentación Q1.000 y universidad Q900. No pide el mes de nuevo sin necesidad. |
| IA03 | ¿Qué deudas tengo y cómo aplicaría la bola de nieve? | Consulta los saldos al corte actual: al 8/11 quedan Q2.050 y Q5.300, total Q7.350; el préstamo familiar ya está pagado. Si se pide 7/11 son Q7.900. Explica el orden y datos contractuales faltantes sin convertir el total en cuota mensual. |
| IA04 | ¿Qué pagos se repetirán y desde cuándo? | Siete plantillas activas desde diciembre; gimnasio inactivo. No confundir plantillas con pagos ejecutados. |
| IA05 | ¿Qué me puedes decir sobre mis planes de ahorro? | Consulta las metas existentes y sus saldos. No responde que carece de datos que sí están registrados. Distingue cumplida, vencida e inactiva. |
| IA06 | ¿Cuál es la tasa exacta de mi préstamo personal y qué día terminaré de pagarlo? | Reconoce que no se registran tasa, mínimos ni cronograma; no inventa amortización ni fecha. Puede citar el saldo conocido. |
| IA07 | ¿Ya cobré los Q700 de freelance previstos para noviembre? | Es un cobro previsto sin pago registrado; no sumarlo a ingresos cobrados. |

Después de cada respuesta, abrir su entrada en **05 Historial**, donde se
conservan fuentes y pasos; el chat principal mantiene lenguaje natural. Registrar la pregunta, respuesta y resultados reales de las
herramientas. Si una respuesta personal no consultó datos actuales ni se apoya
en una fuente recuperada pertinente, marcarla para revisión aunque suene razonable.

## 3. Agente de presupuesto y fuente externa

Elegir **Analiza tu presupuesto**; nueva conversación entre casos.

| Caso | Pregunta para copiar | Resultado que debe verificarse |
|---|---|---|
| IA08 | Identifica pagos individuales de octubre de 2026 hasta Q50 que convenga revisar como posibles gastos hormiga. | 60 pagos, Q1.234. Son candidatos; no afirmar que todo es innecesario o ahorro recuperable. |
| IA09 | Usando octubre de 2026 como base, simula reducir gastos Q412,50 al mes y destinar Q200 adicionales a deuda y Q200 adicionales a ahorro, sin ingreso adicional. | Disponible base Q73; escenario Q85,50. Cálculo del backend, supuestos explícitos y ninguna escritura financiera. |
| IA10 | Consulta mis ingresos, gastos, ahorro y disponible de octubre de 2026. Consulta la inflación anual de Guatemala de 2025 en Banco Mundial. Explica la diferencia de períodos y cita las fuentes y la fecha de consulta. | Q7.250/Q7.177/Q0/Q73, consulta interna y herramienta externa `inflation`. Año publicado, fuente y fecha. No presentar inflación 2025 como inflación mensual ni pronóstico. |

IA10 es el recorrido académico de agente con fuente externa. En Historial debe
verse la herramienta compuesta `budget_external_review` o los pasos separados
de flujo e inflación, sus resultados y llamadas al proveedor. El recorrido
compuesto puede resolver la selección y explicación en dos inferencias; no
exigir artificialmente muchas rondas para considerar que hubo varios pasos.
Si la API externa falla, reconocerlo es correcto como manejo de error, pero la
prueba completa de integración queda pendiente hasta obtener un dato válido.

## 4. Agente de metas, capacidad y escenarios

Elegir **Explora tus metas**.

1. Nueva conversación y preguntar:

   > ¿Qué debería hacer para cumplir mis metas de ahorro dado mi contexto actual? Usa octubre de 2026 como mes cerrado de referencia y consulta mis metas actuales.

   Debe recuperar metas y flujo. Bajo un aporte por mes desde noviembre hasta
   el plazo, calcular con los saldos actuales. En la referencia inicial eran
   fondo Q741,67, computadora Q1.025 y diplomado Q550; con computadora Q1.050
   el requerido de esa meta baja a Q862,50 y el total a Q2.154,17. Contrastar la
   necesidad calculada con Q73 de margen observado en octubre.
   El curso cumplido requiere Q0; la meta vencida necesita revisar plazo o
   prioridad. No prometer financiar todas las metas ni usar dos veces el mismo dinero.

2. Nueva conversación y preguntar:

   > Consulta el Fondo de emergencia y su saldo actual. Consulta la referencia USD/GTQ de Banguat. Simula seis meses aportando 750 GTQ mensuales y seis meses aportando 500 GTQ mensuales. Resume ambos saldos finales, si alcanzan la meta, fuentes y fecha.

   Partiendo de Q550: Q5.050 y Q3.550; el primero alcanza Q5.000 y el segundo
   no. Historial: lectura de meta, Banguat y dos cálculos. Pueden figurar en el
   resultado de `goal_external_scenarios` (acciones y referencias) o como pasos
   separados `exchange_rate`, `simulate_goal` o `savings_plan`. La tasa y fecha deben proceder de la
   consulta de Banguat, no de una cifra fijada en esta guía. No opera cambio real.

3. Volver a metas y al tablero: ninguna simulación debe haber creado pagos o aportes.

## 5. Historial, consumo y evidencia local

1. **05 Historial**: filtrar del 01/11/2026 al 30/11/2026 y cada servicio por separado.
2. Abrir las solicitudes realizadas en los pasos 2–4. Deben conservar pregunta,
   respuesta, estado, fuentes, llamadas y resultados intermedios. Las fallidas
   no deben desaparecer para mejorar las cifras.
3. **06 Consultas y consumo**: mismos filtros. Comprobar consultas, llamadas,
   entrada, salida y total. Para cada fila: entrada + salida = total.
4. Una consulta de usuario no equivale a una llamada: un agente puede tener
   varias rondas. CRUD y consultas directas `/advisor/*` no gastan tokens de IA.
5. `Reservados en curso` debe volver a cero al acabar. La cuota usada aumenta
   con todas las rondas, no solamente con la respuesta final. Cuando el proveedor
   no confirma uso, la estimación conservadora se identifica en el historial.
6. Guardar capturas/JSON después del lote. La referencia local debe tomarse inmediatamente antes del lote; las cifras
   históricas de una auditoría anterior no son un resultado esperado fijo.

Las tarjetas personales de cuota son acumuladas y no cambian al filtrar fechas;
la tabla sí se filtra. No comparar esas dos medidas como si fueran iguales.

## 6. Crear un usuario QA aislado y comprobar permisos

1. Cerrar sesión de Ana; entrar como administrador.
2. **07 Administración → Usuarios y cuotas**: crear un usuario llamado
   `QA aceptación`, correo `qa.20261108@example.test`, rol `user`, cuota **0**.
   El titular elige una contraseña de prueba de al menos 16 caracteres. No copiarla
   en capturas o entregables. Si ya existe esa cuenta, reutilizarla anotando su estado.
3. Cerrar sesión e iniciar con QA: sin datos financieros propios; sin Administración.
4. Intentar una pregunta IA: bloqueo por cuota antes de llamar al proveedor.
   No debe consumirse Groq. Esta cuenta no se usa para eludir la cuota de Ana.
5. En Swagger con el token de QA, intentar historial con `user_id` de Ana:
   403. Consultar sus propias metas: vacío. Leer guías educativas globales es
   esperable; ver registros financieros de Ana sería un fallo de aislamiento.

## 7. CRUD, abonos, validaciones y arrastre con QA

1. En **01 Mis finanzas**, agosto de 2026, crear categoría de egreso `QA gastos`.
2. Intentar crear `qa gastos`: rechazo de duplicado sin distinguir mayúsculas.
3. Crear compromiso `QA pago parcial`, Q100, fecha 10/08/2026. Editarlo a Q120
   antes de abonar. Debe quedar pendiente y permitir edición.
4. **Registrar abono** Q30, fecha 10/08/2026: ejecutado Q30, pendiente Q90, estado Parcial.
5. Intentar Q90,01: rechazo sin alterar el abono previo ni el saldo.
6. Abrir septiembre: el mismo compromiso debe aparecer como Arrastre, sin
   convertirse en una segunda obligación. Repetir navegación: no se duplica.
7. Abonar Q90 con fecha 12/08/2026: total Q120, saldo Q0. En agosto aparece
   Completado; ya no debe arrastrarse como pendiente a septiembre.
8. El compromiso pagado no debe poder editarse ni anularse. El backend también
   debe rechazar esas operaciones si se intentan por API.
9. Crear `QA anulación` sin abonos y pulsar **Anular**: desaparece del tablero activo.
10. Crear categoría sin historial `QA temporal`, editar su nombre e inactivarla:
    conserva referencia administrativa y deja de sugerirse al crear registros.
11. Como QA no tiene ingresos ni ahorro en agosto, el flujo de ese mes termina
    con Q120 de egresos y disponible −Q120. No afecta los meses de Ana.

Anotar las fechas reales elegidas. Si se registra el pago hoy en vez de agosto,
el egreso corresponde al mes de hoy; sería incorrecto esperar los mismos KPI.

## 8. Ahorro y recurrentes con QA

1. **02 Metas de ahorro**: crear `QA ahorro`, meta Q100, plazo 31/12/2026.
2. Registrar +Q40 el 10/08/2026 y −Q10 el 11/08/2026: saldo Q30.
3. Intentar retirar Q30,01: rechazo. Retirar Q30 el 12/08: saldo Q0.
4. **Ver movimientos** conserva aportes y retiros; el ahorro neto de QA en agosto
   es Q0. Editar nombre/plazo e inactivar la meta; un nuevo movimiento debe rechazarse.
5. **03 Recurrentes**: crear `QA mensual`, categoría QA gastos, Q30, inicio
   01/01/2027. No debe generar partidas anteriores a ese inicio.
6. Abrir enero de 2027: una instancia QA por Q30. Recargar: mismo ID/cantidad.
   La cuenta QA no tiene las siete plantillas de Ana.
7. Editar el monto de la plantilla a Q40: enero conserva Q30. Abrir febrero:
   nueva instancia Q40. Inactivar la plantilla; marzo no debe generar otra.
8. Anular las instancias QA sin pagos de enero y febrero si se desea limpiar
   pendientes; conservar evidencia y la plantilla inactiva.

La edición de `start_month` debe conservar el nuevo inicio normalizado al día 1.
Comprobarlo mediante GET después del PUT. Cambiarlo a un mes futuro no borra ni
reescribe instancias generadas; comprobar los meses pendientes de generación.
El campo ignorado de la revisión anterior se considera corregido solo después
de aprobar este ensayo en la versión que se entrega.

## 9. Administración y corpus

Entrar como administrador después de cerrar la sesión QA.

1. Encontrar QA, editar su nombre, desactivarlo; su login debe fallar. Reactivarlo
   si se necesita continuar y desactivarlo al terminar. No modificar su contraseña.
2. **Servicios de IA**: anotar valores de presupuesto; desactivarlo y comprobar
   que Ana no puede usarlo. Reactivarlo y conservar modelo/límites originales.
   La suite aislada cubre también rechazos API de servicio inactivo.
3. Cambiar temporalmente el máximo de salida por un valor válido y restaurarlo.
   No usar esta prueba para eludir cuotas ni elegir modelos facturables.
4. **Fuentes del RAG**: crear una fuente educativa `QA corpus`, procedencia
   `Prueba académica local`, contenido ficticio no personal; editarlo e inactivarlo.
   Debe conservarse y figurar inactivo. No editar los fragmentos gestionados por
   Markdown para esta prueba.
5. Historial y consumo: el administrador puede filtrar por el ID de Ana y por QA;
   Ana solo ve lo propio. Las cuotas son por usuario, no controles del cliente.

6. **Configuraciones IA**: listar las configuraciones como administrador,
   guardar los valores originales y dar de baja una sin solicitudes en curso.
   Debe ocultarse en `/services` y conservarse en `/admin/services` con
   `deleted_at`; el historial permanece legible. El PUT sobre una configuración
   dada de baja se rechaza. Recrearla mediante POST con los mismos ID, nombre
   y valores originales: 201; repetir alta vigente: 409. Los únicos espacios
   implementados son `rag`, `budget` y `goals`; no se crean agentes arbitrarios.
   No es necesario llamar a Groq para probar este CRUD. Restaurar disponibilidad
   y configuración antes de seguir con la demostración.

## 10. Demostración de consumidor externo

Usar Postman instalado localmente o Swagger como apoyo; no introducir claves
privadas en un cliente web de terceros sin revisar el destino.

1. Importar `docs/postman.json`. Para esta ronda cambiar `base_url` a
   `http://127.0.0.1:8000`. Introducir privadamente la contraseña local de Ana.
2. Ejecutar **01 Iniciar sesión**: debe guardar `access_token` automáticamente.
3. **02 Identidad y cuota** y **03 Tablero mensual**: 200 y datos de Ana.
4. Como prueba de funciones sin Groq, enviar:

   ```http
   POST /api/v1/advisor/financial_diagnosis
   Authorization: Bearer <token local>
   Content-Type: application/json
   ```

   ```json
   {"arguments":{"start":"2026-10-01","end":"2026-10-31","as_of":"2026-11-07"}}
   ```

   Deben aparecer flujo, ranking, recurrentes, pendientes, deudas y metas. Los
   totales incluyen todos los registros; `has_more` advierte detalles limitados.
5. Las solicitudes 04–06 consumen IA: basta un ensayo adicional representativo
   desde el cliente externo, sin repetir todo el lote si ya hay evidencia.
6. **07 Historial propio**: encontrar la consulta recién realizada.
7. **08 Consumo agregado** guarda un corte en `report_cutoff` y su forma codificada
   para URL. Ejecutar **09 Datos para Power BI** después: reutiliza ese mismo corte.
8. Si `next_cursor` no es nulo, repetir usage con `after` y los mismos filtros y
   `as_of`, hasta terminar. No sumar solo la primera página.
9. Quitar autorización en una petición protegida: 401. Recuperarla y ejecutar
   **10 Cerrar sesión**. Reutilizar ese token: 401.
10. No exportar la colección con contraseñas, tokens ni credenciales BI cargados.

## 11. Aceptar la versión publicada y CI/CD

Esta parte requiere publicar la ampliación después de corregir los fallos locales.
Una publicación anterior no acredita los módulos incorporados después; usar el
SHA y ejecución registrados en el estado final.

1. Agente: versionar conjuntamente nuevos módulos, guías, pruebas y frontend;
   revisar secretos y reproducir el proyecto en un clon limpio.
2. Agente: enviar la revisión a GitHub y observar **backend → container → deploy**.
   Si un job requerido falla, no continuar con una publicación manual que salte CI.
3. Comprobar la dependencia de deploy de los dos jobs exitosos; registrar una
   ejecución fallida con deploy omitido si se prepara un ensayo negativo aislado.
   No introducir un fallo deliberado en la rama de entrega.
4. Agente: confirmar que `/api/health` público tiene el SHA publicado y base `ok`;
   Swagger debe incluir `/api/v1/advisor/tools`.
5. La publicación de código no importa los datos ni las guías. Preparar una carga
   cloud controlada con credenciales cloud y sin quitar la protección local de
   `backend.demo`. No cambiar la `.env` local para apuntar el laboratorio a Neon.
6. Verificar en Render cuentas/roles, corpus, tres servicios y persistencia. Usar
   los resultados del entorno cloud: no asumir que tiene los importes locales.
7. Repetir como mínimo RAG con seguimiento/insuficiencia, presupuesto con Banco
   Mundial y metas con Banguat y dos escenarios. Registrar consumo y fuentes reales.
8. Revisar que Render, Neon y Groq continúen en Free y que la cuenta institucional
   permita actualizar/exportar Power BI. No añadir tarjeta ni mejorar planes.

## 12. Reporte web, API y Power BI: mismo conjunto y corte

Ejecutar después de las llamadas de aceptación **cloud**. Detener nuevas
consultas IA y esperar a que no queden solicitudes/reservas en curso.

1. Entrar en la aplicación HTTPS como administrador. En **06 Consultas y consumo**,
   fechas 01/11–30/11/2026, todos los servicios. Elegir alcance: todos los usuarios
   o Ana; usar el mismo alcance en API y Power BI. QA no debe mezclarse por accidente.
2. Cliente externo cloud: `GET /api/v1/reports/summary` con esos filtros.
   Guardar `as_of` como **T**. Consultar summary y todas las páginas usage con T
   fijo y mismos filtros, codificando los parámetros de URL.
3. Sumar por servicio solicitudes, llamadas, entrada, salida y total. La web debe
   coincidir durante esta ventana sin nuevas llamadas. La UI no acepta T manual:
   registrar también el corte que muestra y mantener el conjunto sin cambios.
4. Iniciar sesión institucional en Power BI. Abrir `Saldo_Consultas_y_Consumo`.
   La fuente debe ser HTTPS de Render, nunca localhost ni una conexión directa a Neon.
5. Autenticación Basic: cuenta BI cloud y su contraseña privada. No escribirla en M
   ni añadir clave Groq. Las autorizaciones anteriores de Microsoft se conservan.
6. Actualizar el **modelo semántico**, esperar estado completado y refrescar el
   informe. Refrescar solamente la vista no demuestra que se hayan importado datos nuevos.
7. Para un contraste exacto, el agente puede fijar temporalmente `Corte=T` en
   Power Query. `powerbi/consumo.pq` ya conserva un corte por todas sus páginas.
   Si se mantiene el corte dinámico, demostrar que no se completaron solicitudes
   entre los cortes antes de afirmar que comparan la misma cohorte.
8. Probar todos los servicios y cada servicio por separado; un intervalo con
   registros y otro vacío. Filtrar usuario en PBIX si se está comparando solo Ana.
9. Las cinco métricas deben coincidir. Entrada + salida = total; número de
   solicitudes no es número de llamadas. Conservar solicitudes fallidas y uso estimado.
10. Descargar PBIX con **informe y datos/modelo**; comprobar archivo íntegro y
    fuente API. El agente verifica ausencia de secretos y conserva las evidencias.
    Windows Desktop es opcional; no sustituye la comprobación de datos.

Los antiguos 5/15/9.716 pertenecen al corte cloud del 2 de noviembre. Las cifras
locales de auditorías anteriores tampoco son una meta fija: cambian con los ensayos.
No confrontar números de una instalación contra el reporte de la otra.

## 13. Entregables y criterio de cierre

Agente y usuario recorren juntos:

- [ ] Repositorio público clonado desde cero contiene el asesor completo, guías,
      pruebas y workflow; `.env.example` permite configurarlo sin secretos ajenos.
- [ ] Arranque limpio con Docker/Alembic/seed reproducido sin credenciales del equipo original.
- [ ] SQL final y migraciones presentes; datos ficticios suficientes y pasos de
      `backend.demo`/`backend.knowledge` documentados donde correspondan.
- [ ] Suite final aprobada, compilación aprobada, CI/CD del SHA entregado verde.
- [ ] Aplicación/API HTTPS, Swagger y consumo externo comprobados.
- [ ] RAG y dos agentes reales aprobados, con fuentes, memoria, insuficiencia,
      errores y consumo trazable; fallos detectados corregidos y reensayados.
- [ ] CRUD de configuraciones de servicios y edición de inicio de recurrentes
      comprobados en la versión entregada, manteniendo historial e instancias previas.
- [ ] Reporte web/API/Power BI coincidente, filtros verificados y PBIX completo.
- [ ] PDF coherente con alcance, arquitectura, modelo de datos, capturas, pruebas,
      commit de implementación, enlaces y estado final. Comprobar fecha, SHA, modelo, cifras y capturas en el archivo que se entrega.
- [ ] Actualizar README/estado y PDF/PBIX; un commit documental posterior puede
      tener otro SHA, distinguiéndolo del commit de implementación acreditado.
- [ ] Exportaciones y repositorio sin contraseñas, tokens, conexiones privadas ni respaldos.
- [ ] Ensayo de exposición: login → pregunta RAG → agente presupuesto → agente metas
      → historial/consumo → cliente externo → Power BI → archivos entregados.

Registrar por caso: ID, entorno, usuario, fecha/corte, entrada, esperado,
resultado observado, evidencia, estado y corrección/reensayo. Un texto plausible,
una captura antigua o un ZIP existente no sustituyen la prueba correspondiente.
