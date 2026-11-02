# Saldo · Finanzas personales con IA

Proyecto académico. Moneda operativa GTQ; los escenarios USD/GTQ son simulaciones.
Los pagos son registros manuales: no hay conexión bancaria ni transferencias reales.

## Alcance aprobado

Ver [especificación](docs/alcance.md) y [matriz de cumplimiento](docs/cumplimiento.md).
El PRD original en Recursos se conserva como visión de producto futura.

## Desarrollo

1. Copiar `.env.example` a `.env` y establecer contraseñas propias.
2. `docker compose up --build -d --wait`
3. `docker compose exec app python -m backend.seed` (solo datos ficticios).
4. Abrir http://localhost:8000 y http://localhost:8000/docs.
5. `docker compose exec app pytest -q` usa una BD de pruebas separada.

No versionar `.env`, claves, credenciales de BI ni respaldos de datos reales.
El proveedor Groq permanece desactivado mientras no exista `GROQ_API_KEY`.

## Estado

[Aplicación HTTPS](https://saldo-academico.onrender.com) ·
[API / Swagger](https://saldo-academico.onrender.com/docs) ·
[GitHub Actions](https://github.com/mariofrodm/saldo-academico/actions).

Consultar `docs/estado.md` para distinguir verificaciones terminadas y pendientes.
Render y Neon usan Free; nunca añadir métodos de pago para este proyecto.
Render puede tardar al despertar tras inactividad. Las credenciales de prueba
se entregan localmente, fuera del repositorio público.
