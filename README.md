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

## Entrega y demostración

- [Informe técnico y evidencias (PDF)](output/pdf/Informe_Saldo_Academico.pdf).
- [Informe completo Power BI (PBIX)](powerbi/Saldo_Consultas_y_Consumo.pbix).
- [Colección Postman](docs/postman.json), con URL HTTPS publicada; establecer
  la contraseña localmente. Para localhost cambiar la variable `base_url`.
- [Portabilidad Ubuntu/Windows y recuperación](docs/portabilidad.md).
- [Operación y cuotas gratuitas](docs/operacion.md).

El PBIX se creó, actualizó y descargó desde Power BI web en Ubuntu. Se leyó su
modelo localmente: 5 solicitudes, 15 llamadas y 9.716 tokens al corte de entrega.
Los filtros por fecha y servicio coinciden con la web. Abrirlo en Power BI
Desktop requiere Windows y una versión actual; ese ensayo no se ejecutó.

La consulta `powerbi/consumo.pq` importa noviembre de 2026. Cambiar FechaDesde y
FechaHasta para otros períodos; las credenciales Basic se configuran fuera de M.
El PDF es una evidencia fechada, no un monitor de los consumos posteriores.
