# Estado verificable — 2 de noviembre de 2026

## Completado y comprobado

- Alcance académico acotado y matriz de cumplimiento; PRD original conservado.
- Aplicación React/TypeScript y FastAPI construida y ejecutada en Docker Ubuntu.
- Autenticación, roles, aislamiento, CRUD del dominio/administración, pagos parciales,
  ahorro, recurrentes idempotentes, corpus RAG, historial y reporte de consumo.
- 27 pruebas automatizadas aprobadas contra PostgreSQL 17 aislado.
- Una advertencia de deprecación Starlette/httpx en el cliente de pruebas; no afecta
  resultados. No se ejecutan llamadas de pago o a Groq durante la suite.
- Fuentes reales Banco Mundial y Banguat accesibles desde backend.
- Neon Free, Virginia, PostgreSQL 18; conexión directa/agrupada con TLS verify-full
  verificadas en cliente libpq; migraciones y seed ficticio cargados.
- Groq Free, clave propia del proyecto autorizada y guardada fuera de Git, vence
  02/12/2026. Los tres servicios probados con Groq real y fuentes.
- Agente de metas: consulta de meta, Banguat y dos simulaciones; cinco llamadas
  con respuesta final, todas contabilizadas. Límite configurable de hasta seis.
- Repositorio público creado con confirmación del usuario. GitHub CLI amplio
  cancelado; clave SSH exclusiva del repositorio confirmada y probada.
- Workflow CI/CD escrito: tests + contenedor antes de deploy por SHA.
- Código publicado en mariofrodm/saldo-academico. GitHub Actions ejecutó tests
  y arranque del contenedor satisfactoriamente (run 41421455428, commit 99ca66c).
- Primer Render Free publicado: https://saldo-academico.onrender.com;
  health HTTPS confirma el commit 99ca66c y acceso a Neon.
- Hook privado de Render guardado como secreto de Actions; APP_URL y
  DEPLOY_ENABLED configurados. Falta comprobar el ciclo completo automático.
- Colección Postman y consulta Power Query paginada sin credenciales preparadas.

## No dar por terminado todavía

- Comprobar el ciclo completo de CI/CD desde un nuevo commit.
- Comprobar UI/API publicadas, persistencia tras redeploy y uso externo.
- Conectar Power BI a la API definitiva, contrastar totales y descargar PBIX final.
- Completar PDF de evidencias y ensayo de entrega.

Las pruebas previas de Power BI están en ../pruebas/powerbi; no sustituyen el PBIX
conectado al proyecto. Los resultados locales detallados están excluidos de Git
para no publicar sesiones, trazas operativas o datos potencialmente sensibles.
