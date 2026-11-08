# Matriz de cumplimiento

Cada estado se acredita en `estado.md`; una fila es un criterio, no una afirmación
de que esté implementada o publicada.

| ID | Requisito | Prueba/evidencia exigida |
|---|---|---|
| A01 | Objetivo, usuarios, fuentes y 3 servicios | alcance y diagrama GUI/API/BI |
| A02 | Roles y aislamiento | 401/403 y acceso cruzado denegado |
| A03 | CRUD usuarios, dominio, corpus y servicios | pruebas API y demostración GUI |
| A04 | RAG con BD, fuentes, memoria e insuficiencia | pruebas con y sin fuentes; conversación |
| A05 | Agente presupuesto con datos externos | selección de herramientas, varios pasos y fuentes |
| A06 | Agente metas con datos externos | consulta de meta, tipo de cambio y simulaciones |
| A07 | Historial por usuario y global admin | filtros y aislamiento comprobados |
| A08 | Cuotas, tokens de todas las rondas y bloqueo | concurrencia, errores y límites |
| A09 | API externa autenticada, Swagger/Postman | colección y consumo externo real |
| A10 | Reporte web de consultas/tokens | datos deterministas y filtros |
| A11 | Power BI consume API y coincide con web | refresh, comparación y PBIX definitivo |
| A12 | Pruebas IA/historial/consumo automatizadas | salida de CI con proveedor simulado |
| A13 | Aplicación/API cloud y persistencia | HTTPS, reinicio y health SHA |
| A14 | CI/CD solo con pruebas exitosas | commit exacto y fallo que no despliega |
| A15 | SQL/seed, PDF, repositorio y enlaces | ensayo de entrega/restauración |

La revisión actual se cierra en el orden: correcciones y suite → publicación
del SHA probado → aceptación cloud de servicios y API → contraste Power BI →
PBIX/PDF/documentación → clon y recuperación. El estado fechado de cada corte
está en `estado.md`; no asignar 100 % por la mera existencia de archivos.
