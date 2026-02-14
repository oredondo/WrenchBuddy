# WrenchBuddy

Aplicacion de mantenimiento de vehiculos con recomendaciones IA. Enfoque MVP moto-first, extensible a coches.

## Stack

- **Backend**: Django 6.0.2 + Django REST Framework 3.16.1
- **Base de datos**: SQLite (desarrollo) / PostgreSQL (produccion)
- **Auth**: Session-based con email como identificador principal
- **Testing**: pytest + pytest-django

## Estructura del proyecto

```
WrenchBuddy/
├── wrench_buddy/          # Configuracion Django
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── users/                 # Autenticacion y perfil de usuario
├── vehicles/              # CRUD de vehiculos
├── maintenance/           # Eventos, tareas y catalogo de mantenimiento
├── ai_assistant/          # Recomendaciones IA (en desarrollo)
├── manage.py
└── requirements.txt
```

## Modelo de datos

- **Vehicle**: Vehiculo del usuario (moto o coche), con marca, modelo, ano, km actuales y tipo de uso.
- **MaintenanceEvent**: Registro de mantenimiento realizado por el usuario (cambio de aceite, revision frenos, etc.).
- **MaintenanceTask**: Tarea sugerida por la IA con prioridad, km/fecha estimados y estado (pendiente, completada, descartada).
- **TaskCatalog**: Catalogo de tareas por tipo de vehiculo con intervalos por defecto y flag de seguridad critica.

## Flujo principal

1. El usuario registra su vehiculo y km actuales
2. Registra mantenimientos pasados (MaintenanceEvent)
3. La IA analiza catalogo + historial + km y genera tareas pendientes (MaintenanceTask)
4. El usuario marca una tarea como completada, lo que crea un MaintenanceEvent vinculado

## API Endpoints

| Endpoint | Descripcion |
|---|---|
| `POST /api/users/` | Registro de usuario |
| `GET /api/users/me/` | Perfil del usuario autenticado |
| `POST /api-auth/login/` | Login (session) |
| `POST /api-auth/logout/` | Logout |
| `GET/POST /api/v1/vehicles/` | Listar / crear vehiculos |
| `GET/PUT/DELETE /api/v1/vehicles/:id/` | Detalle / editar / eliminar vehiculo |
| `GET/POST /api/v1/maintenance/events/` | Listar / crear eventos de mantenimiento |
| `GET /api/v1/maintenance/catalog/` | Catalogo de tareas |
| `GET/POST /api/v1/maintenance/tasks/` | Listar / crear tareas IA |
| `POST /api/v1/maintenance/tasks/:id/complete/` | Completar tarea (crea evento) |
| `POST /api/v1/maintenance/tasks/:id/dismiss/` | Descartar tarea |

## Instalacion y desarrollo

```bash
# Crear y activar virtual environment
python -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Aplicar migraciones
python wrench_buddy/manage.py migrate

# Crear superusuario
python wrench_buddy/manage.py createsuperuser

# Servidor de desarrollo
python wrench_buddy/manage.py runserver
```

## Tests

```bash
# Ejecutar todos los tests
cd wrench_buddy && pytest

# Test de una app especifica
pytest users/
pytest vehicles/
pytest maintenance/

# Test especifico
python manage.py test app.tests.TestClass.test_method
```

## Task codes (MVP - Motos)

| Codigo | Descripcion |
|---|---|
| `oil_change` | Cambio aceite + filtro |
| `chain_service` | Limpieza/tensado cadena |
| `tire_check` | Revision neumaticos |
| `brake_check` | Revision frenos |
| `coolant_change` | Cambio refrigerante |
| `spark_plugs` | Cambio bujias |
| `air_filter` | Filtro aire |
| `itv` | ITV/revision tecnica |
