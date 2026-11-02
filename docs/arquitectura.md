# Arquitectura de Saldo

```mermaid
flowchart LR
    U[Usuario o administrador] --> W[React · TypeScript]
    W -->|HTTPS · cookie HttpOnly y CSRF| API[FastAPI · REST y Swagger]
    P[Postman / cliente externo] -->|HTTPS · sesión Bearer| API
    BI[Power BI web o Desktop] -->|HTTPS · Basic solo reportes| API
    API -->|TLS verify-full| PG[(PostgreSQL · Neon Free)]
    API --> R[RAG · recuperación por usuario y corpus]
    API --> A[Agentes · herramientas permitidas]
    R --> PG
    R --> G[Groq Free]
    A --> G
    A --> WB[Banco Mundial · inflación anual]
    A --> BG[Banguat · referencia USD/GTQ]
    A --> C[Cálculos Decimal]
    GH[GitHub · main] --> T[Actions · pruebas y contenedor]
    T -->|Solo success · SHA exacto| RD[Render Free · contenedor React + API]
```

El bloque React/API se sirve desde un solo origen. No hay disco persistente en
Render: movimientos, corpus, sesiones, herramientas, conversaciones y consumo
se conservan en PostgreSQL. El frontend no recibe claves Groq o de la BD.

## Modelo relacional

```mermaid
erDiagram
    users ||--o{ sessions : autentica
    users ||--o{ categories : posee
    users ||--o{ recurring : planifica
    users ||--o{ obligations : registra
    categories ||--o{ obligations : clasifica
    recurring ||--o{ obligations : genera
    obligations ||--o{ payments : ejecuta
    users ||--o{ goals : define
    goals ||--o{ savings : recibe
    users ||--o{ conversations : consulta
    services ||--o{ conversations : atiende
    conversations ||--o{ requests : conserva
    requests ||--o{ provider_calls : consume
    requests ||--o{ tool_runs : consulta
    users ||--o{ audit : registra
```

`knowledge` alimenta RAG. `budgets` registra reservas de organización por día y
minuto; `users` conserva cuota acumulada por usuario. Las reservas en curso
quedan en `requests`: tras una interrupción se concilian conservadoramente,
sin borrar consumos desconocidos. Un proceso de recuperación al arrancar cierra
llamadas pendientes de más de 15 minutos y solicitudes sin llamada de más de 30.

## Reporterías

Web y Power BI consumen `/api/v1/reports/summary` y `/usage`, con las mismas
reglas de fecha Guatemala, servicio y permisos. Solo incluyen solicitudes
terminadas antes de `as_of`. `/usage` pagina por `(created_at,id)`; las llamadas
se agregan por solicitud para no inflar el número de peticiones del usuario.

## Entorno

Local y CI: PostgreSQL 17. Neon creado en PostgreSQL 18. Ambas versiones soportan
el SQL usado; la migración cloud se verifica por separado. Docker Compose limita
la aplicación a 512 MB y publica únicamente 127.0.0.1:8000. Subdominio HTTPS de
Render para la publicación. Fabric no interviene en el backend.
