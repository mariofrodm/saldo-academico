# Ubuntu, Windows y recuperación

El desarrollo y el servicio publicado pueden mantenerse en Ubuntu. Para usar
Power BI Desktop en Windows basta el PBIX, la API HTTPS y la credencial de
lectura de reportes: no se necesita trasladar PostgreSQL, Render ni Groq.

## Usar Power BI Desktop desde Windows

1. Utilizar un Windows ya disponible y compatible. Instalar la versión actual
   de Power BI Desktop de 64 bits desde Microsoft; no adquirir licencias para
   esta práctica.
2. Abrir el PBIX del proyecto. En la configuración del origen, usar
   `https://saldo-academico.onrender.com` y autenticación Basic con
   `bi@example.test`. La contraseña se entrega por separado, nunca en M,
   capturas, repositorio o informe PDF.
3. Si se crea el informe desde cero, usar `powerbi/consumo.pq`; el origen es la
   API del proyecto, que ya consulta Neon. No crear una conexión directa desde
   Power BI a Neon ni introducir la clave de Groq en Power BI.
4. Actualizar y comparar consultas y tokens con el reporte web, usando los
   mismos filtros de fecha, servicio y corte de datos. Guardar el PBIX completo.

La documentación oficial de Microsoft distribuye Desktop para Windows de
64 bits. El ensayo de este proyecto se realizó desde la web en Ubuntu; esta
auditoría no afirma haber ejecutado Power BI Desktop en Windows.
[Descarga y requisitos de Power BI Desktop](https://learn.microsoft.com/en-us/power-bi/fundamentals/desktop-get-the-desktop).

## Reproducir la aplicación en otra máquina

La ruta de menor trabajo para la demostración es abrir la aplicación HTTPS
publicada. Si hace falta desarrollar o ejecutar una copia independiente en
Windows, usar Docker Desktop con el motor Linux sobre WSL 2 y Git. En Ubuntu
bastan Docker Engine con Compose y Git. No hace falta instalar Python, Node o
PostgreSQL globalmente.

Docker permite el uso gratuito de Desktop para educación. Verificar que el
equipo cumple los requisitos de Windows, WSL 2, memoria y virtualización antes
de instalar. La licencia de Windows no se incluye en este proyecto; utilizar
un equipo ya licenciado. [Instalación de Docker en Windows](https://docs.docker.com/desktop/setup/install/windows-install/)
y [motor WSL 2](https://docs.docker.com/desktop/features/wsl/).

Desde una terminal Ubuntu, incluida Ubuntu sobre WSL 2:

```sh
git clone https://github.com/mariofrodm/saldo-academico.git
cd saldo-academico
cp .env.example .env
```

Editar `.env` localmente antes de continuar:

- Crear cuatro contraseñas independientes: PostgreSQL, administración, demo y
  BI. Para las tres cuentas de la aplicación se exigen al menos 16 caracteres
  y no se permite el prefijo `CAMBIAR`. Usar valores aleatorios de 32 caracteres
  alfanuméricos simplifica la URI de PostgreSQL; caracteres especiales en la
  contraseña de esa URI deben codificarse correctamente.
- Reemplazar la contraseña en `POSTGRES_PASSWORD` y en `DATABASE_URL` por el
  mismo valor. Mantener `@db:5432/saldo` para esta copia local.
- Mantener `APP_ENV=local` y `COOKIE_SECURE=false` para localhost.
- Dejar `GROQ_API_KEY` vacía permite probar autenticación, datos, interfaz e
  informes. La IA real requiere guardar localmente una clave de Groq Free con
  cuota disponible. Nunca activar un plan de pago ni versionar la clave.

```sh
docker compose -p saldo_academico up --build -d --wait
docker compose -p saldo_academico exec app python -m backend.seed
```

Abrir `http://localhost:8000` y `http://localhost:8000/docs`. Las cuentas iniciales
son `admin@example.test`, `demo@example.test` y `bi@example.test`, con las
contraseñas propias del archivo `.env`. Los datos son ficticios. El puerto
8000 solo se publica en loopback y PostgreSQL no publica ningún puerto.

Para ejecutar las pruebas sin consumir Groq:

```sh
docker compose -p saldo_academico exec app pytest -q
```

Las pruebas crean una base local independiente. No ejecutarlas contra Neon.
El volumen de PostgreSQL no viaja en Git. Para conservar datos al apagar,
utilizar `docker compose -p saldo_academico down` sin `--volumes`.

Una copia para desarrollo debe usar su propia `.env`. Si se necesita operar
los servicios cloud existentes desde otra máquina, transferir su configuración
privada por un medio seguro fuera de Git y mantenerla separada. No sustituir
por la conexión Neon la `DATABASE_URL` de esta receta local ni iniciar por
accidente un segundo frontend sobre la base cloud.

## Esquema y datos para el revisor

La ruta recomendada es Compose: el arranque de la aplicación ejecuta
`alembic upgrade head`, que aplica `migrations/` en orden. Después,
`python -m backend.seed` carga las cuentas, servicios y datos ficticios. Las
contraseñas vienen del entorno y se guardan como hashes nuevos; no se publica
un SQL con hashes o contraseñas de las cuentas utilizadas en la demostración.

`backend/schema.sql` contiene el DDL final como script de creación para una
base vacía. Es una alternativa a ejecutar las migraciones desde cero, no un
paso previo a ellas. Si un revisor elige importar manualmente ese SQL completo,
debe ejecutar `python -m alembic stamp head` en el mismo entorno y contra esa
base **antes** del primer arranque normal de la aplicación; después ejecuta el
seed. `stamp` solo marca la revisión: no crea ni verifica tablas, por lo que
corresponde exclusivamente al esquema final completo y de la misma revisión
del repositorio. Para cualquier otra base, usar la ruta de migraciones.

## Respaldo verificado

El ensayo local del 02/11/2026 creó un respaldo PostgreSQL custom y lo restauró
con `pg_restore --exit-on-error --no-owner --no-privileges` en una base nueva
temporal. Se comprobaron:

- 16 tablas de dominio más `alembic_version`, con iguales conteos de filas.
- 19 claves foráneas validadas y todas las restricciones iguales.
- Revisión Alembic `0003` conservada.
- Eliminación únicamente de la base temporal; la base original y su volumen
  permanecen.

La evidencia sanitizada está en `evidencias-locales/portabilidad-final.json`.
El respaldo privado `evidencias-locales/respaldo-local.dump` tiene permisos 0600,
está excluido de Git y no es un entregable público: aunque los datos son
ficticios, incluye hashes y registros de sesión. Una recuperación real debe
hacerse primero en una base nueva separada, nunca sobreescribir la existente
como prueba ni ejecutar `down --volumes`.

La restauración verificada fue PostgreSQL 17.11 → 17.11 en Linux. Neon utiliza
PostgreSQL 18: un respaldo de Neon requiere herramientas de esa versión o más
recientes y un destino compatible; este ensayo no acredita importar un dump
18 en PostgreSQL 17. Windows físico tampoco se ejecutó en esta auditoría.

## Repositorio independiente del equipo

Se comprobó un clon HTTPS público desde una carpeta nueva, sin credenciales,
con Dockerfile, Compose, dependencias fijadas, frontend, migraciones y CI.
El estado auditado tenía 43 archivos versionados y ningún `.env` real, clave
privada o respaldo. La clave SSH local sirve únicamente para publicar cambios;
no es necesaria para clonar, compilar o usar el proyecto y no debe copiarse
como parte del código.
