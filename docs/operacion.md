# Operación con costo cero

## Preparar otra máquina

Clonar el repositorio, crear `.env` a partir de `.env.example`, establecer cuatro
contraseñas independientes y ejecutar Compose según README. La DB local está
en un volumen, nunca ejecutar `down --volumes` si se desean conservar los datos.
No hay necesidad de instalar PostgreSQL o Python globalmente para usar Docker.

`backend/schema.sql` es el esquema final para una BD vacía; `alembic upgrade head`
es la ruta recomendada y versionada. No ejecutar ambas rutas en la misma BD.
`python -m backend.seed` carga exclusivamente datos ficticios e inicia servicios.
El seed no cambia contraseñas de usuarios existentes ni imprime sus valores.

## Credenciales

Usuarios iniciales: `admin@example.test`, `demo@example.test`, `bi@example.test`.
Las contraseñas locales están en `.env`; las cloud, independientes, en
`.env.cloud`. Ambos archivos están excluidos de Git y tienen permisos 0600.
Groq solo en backend; clave con vencimiento el 02/12/2026. No añadir métodos de
pago ni sustituir Free por Developer. No subir estos archivos como entregables.

GitHub CLI no se renovó: la revisión automática rechazó sus permisos amplios.
La alternativa propuesta/confirmada es una clave SSH por repositorio, guardada
en `.local-secrets`, sin cambiar el acceso a otros repositorios o a la cuenta.
Verificar el estado final en `estado.md`. La clave de publicación debe retirarse
desde Settings → Deploy keys cuando termine el trabajo académico. No expira sola.

## Despliegue

Render: Web Service Docker, Free, Virginia, repositorio público, rama main.
Variables: DATABASE_URL agrupada, DATABASE_URL_DIRECT para migración,
GROQ_API_KEY, APP_ENV=production y COOKIE_SECURE=true. El seed se ejecuta
desde el entorno local con la conexión cloud antes de publicar. Sus contraseñas
no se necesitan en Render: la base conserva exclusivamente sus hashes.
La URL de Neon exige sslmode=verify-full y una CA válida; la app usa certifi.
El health devuelve RENDER_GIT_COMMIT para verificar el commit servido.

Tras el primer despliegue aprobado, configurar el hook secreto en GitHub Actions
como RENDER_DEPLOY_HOOK, variable APP_URL y DEPLOY_ENABLED=true. Auto-deploy de
Render debe quedar apagado. El workflow valida backend, compila React y arranca
el contenedor; el deploy exige success de ambos jobs y ref=SHA. Un HTTP 200/202
del hook solo significa que se solicitó; el job espera health y SHA correctos.
Configurar environment academic-free en GitHub; nunca imprimir la URL del hook.

Render duerme tras inactividad: abrir la aplicación antes de la demostración.
Neon se suspende por inactividad y tiene cuotas finitas. No mantener servicios
despiertos con pings artificiales ni contratar cron o discos persistentes.

## Pruebas y recuperación

`docker compose exec app pytest -q` crea una BD temporal independiente y la retira
al terminar. Las pruebas simulan Groq y fuentes públicas: no consumen cuota IA.
No ejecutar pytest con la conexión Neon: requiere CREATE DATABASE y está pensado
para PostgreSQL local/CI. Las pruebas cloud son de integración, no de borrado.

`docker compose exec app python -m backend.recover` concilia solicitudes
interrumpidas antiguas; no reintenta llamadas ni regala tokens cuyo consumo
no se pudo confirmar. Un 429 se muestra como bloqueo y queda en el historial.

Para respaldar, usar pg_dump con la conexión directa y guardar fuera de Git.
Nunca escribir la contraseña en una línea de comandos o registrar la URI.
Probar restauración en una BD local separada antes de la entrega.

## Validación Power BI

Usar `powerbi/consumo.pq`, reemplazar BaseUrl y configurar Basic en el diálogo de
credenciales con bi@example.test. No escribir contraseña en M. Importar todas
las páginas. Comparar por fecha/servicio y el mismo as_of del endpoint. Descargar
PBIX con informe y datos; repetir refresh y comprobar filtros/totales.
El archivo definitivo todavía debe verificarse; los PBIX previos son ensayos.
