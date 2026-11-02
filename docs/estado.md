# Estado verificable - 2 de noviembre de 2026

## Implementado y comprobado

- React/TypeScript + FastAPI en Docker Ubuntu; moneda operativa GTQ.
- Autenticación, roles, aislamiento, administración, categorías, compromisos,
  pagos parciales, ahorro, recurrentes idempotentes, corpus RAG e historial.
- 27 pruebas automatizadas contra PostgreSQL 17 aislado. Groq y fuentes
  públicas simuladas en CI; una advertencia de deprecación no bloqueante.
- Neon Free Virginia, PostgreSQL 18.6, conexiones directa/agrupada con TLS
  verificado en cliente libpq. Migraciones 0001-0003 y datos ficticios cargados.
- Groq Free: los tres servicios probados con llamadas reales desde Render.
  RAG con fuente propia; presupuesto con movimientos e inflación histórica
  2025; metas con Banguat y dos simulaciones calculadas por herramientas.
- Resultados faltantes se explican: la inflación anual 2026 no publicada y una
  meta inexistente no se inventaron. Esas consultas siguen contabilizadas.
- API HTTPS pública con autenticación, Swagger y colección Postman.
- CI/CD completo exitoso: backend, contenedor y deploy, ejecución
  [41423307877](https://github.com/mariofrodm/saldo-academico/actions/runs/41423307877),
  commit verificado `0c5d2f7b0df16b643fc070056fd57563e0b2bedf`.
  El workflow conserva el secreto del hook y fija el SHA probado. Render
  auto-deploy está Off; Actions publica después de aprobar ambos jobs.
- Aplicación: https://saldo-academico.onrender.com. Login, cookies Secure,
  acceso BI de solo lectura y datos conservados tras redeploy comprobados.
- Power BI conectado a la API definitiva con Basic guardado en Microsoft,
  paginación y corte fijo por actualización, sin gateway local.
  Actualización a petición completada 02/11/2026 09:51:24, Guatemala.
- Web/API/Power BI/PBIX coinciden: 5 solicitudes, 15 llamadas, 8.445 tokens
  de entrada + 1.271 de salida = 9.716. Filtro presupuesto: 2/6/3.669.
- PBIX completo en `powerbi/Saldo_Consultas_y_Consumo.pbix`: ZIP íntegro,
  modelo importado y consulta M decodificados desde Ubuntu con PBIXRay.
  Cinco IDs únicos; filtros de fecha/servicio y agregaciones verificados.
  Ningún secreto local encontrado en ZIP ni modelo ABF descomprimido.
- Respaldo/restauración local comprobados: 16 tablas de dominio más Alembic,
  19 claves foráneas y 57 restricciones iguales. Base original conservada.
- Clon público sin credenciales comprobado; instrucciones en portabilidad.md.
- PDF técnico de arquitectura, modelo y evidencias en
  `output/pdf/Informe_Saldo_Academico.pdf`.

## Límites y preparación de la defensa

- Todo se realizó desde Ubuntu. No se ejecutó Power BI Desktop en Windows;
  abrir/actualizar allí sigue siendo una comprobación opcional en una versión
  actual compatible con el PBIX descargado, sin migrar servicios.
- Power BI/Fabric mostraba 17 días restantes de prueba al verificar. No asumir
  que los permisos/licencias o las cuotas Free sean indefinidos.
- Render puede dormir por inactividad y Neon tiene cuotas y suspensión.
  Abrir antes de la defensa; no usar pings artificiales ni activar pagos.
- Groq tiene cuotas finitas; la clave del proyecto vence el 02/12/2026.
  La cuenta demo conserva 10.284 tokens del límite interno de 20.000 al corte.
- La suite no equivale a una auditoría de seguridad ni a pruebas de alta carga.
  Ensayar la exposición y preparar credenciales locales para el docente.

Los resultados detallados, capturas y respaldos están en evidencias-locales,
excluidos de Git. El PDF/PBIX de entrega solo contiene datos ficticios.
La evidencia refleja los commits indicados; cambios documentales posteriores
pueden producir un nuevo SHA de despliegue sin alterar la implementación.
