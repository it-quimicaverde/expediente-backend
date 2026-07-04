# Expediente — Backend

## 1. Base de datos (Neon) — 10 minutos
1. Crea cuenta en https://neon.tech (gratis, sin tarjeta)
2. Crea un proyecto nuevo → copia el "Connection string"
3. En tu máquina, corre el archivo `schema.sql` contra esa conexión:
   ```bash
   psql "postgresql://usuario:password@host/dbname?sslmode=require" -f schema.sql
   ```
   (si no tienes `psql` instalado, puedes correr el contenido de schema.sql
   directamente desde el "SQL Editor" que trae el dashboard de Neon)

## 2. Backend local — 15 minutos
```bash
python -m venv venv
source venv/bin/activate        # en Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # y pega tu DATABASE_URL real de Neon
uvicorn app.main:app --reload
```
Abre http://localhost:8000/docs — ahí ya puedes probar los endpoints desde el navegador
(Swagger UI, viene incluido gratis con FastAPI).

## 3. Cargar el catálogo de trámites
El CSV `catalogo_tramites_tipo_tramite.csv` que ya tienes se carga a la tabla
`tipo_tramite` — dime cuando lleguemos a este paso y te armo el script de importación.

## 4. Subir a GitHub y desplegar en Render
1. Sube esta carpeta a un repo nuevo en GitHub
2. En https://render.com → "New Web Service" → conecta el repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Agrega la variable de entorno `DATABASE_URL` con tu string de Neon
6. Deploy — Render te da una URL pública en unos minutos

## Endpoints ya listos para probar
- `GET  /health` — verifica que el servidor responde
- `GET  /empresas?q=manantial` — busca empresas por nombre
- `POST /empresas` — crea una empresa cliente
- `GET  /tipos-tramite?categoria=alimentos` — catálogo filtrado por categoría
- `POST /tramites` — crea un trámite (autocompleta vencimiento y checklist)
- `GET  /dashboard/proximos-vencer?dias=30` — lo que ves en el dashboard
- `GET  /empresas/{id}/tramites` — historial de una empresa (la ficha)

## Pendiente para las próximas sesiones
- Autenticación real (login + JWT) — hoy los endpoints no están protegidos
- Job de alertas automáticas (60/30/15 días)
- Permisos por rol (admin ve todo, gestor solo sus empresas asignadas)
