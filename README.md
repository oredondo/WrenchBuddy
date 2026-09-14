# 🔧 WrenchBuddy

> Intelligent vehicle maintenance platform featuring AI-powered predictive recommendations (RAG + Computer Vision), expense analytics, and a social garage community. Motorcycle-first focus, extensible to cars.

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![Django](https://img.shields.io/badge/Django-6.0.2-092E20?logo=django)
![DRF](https://img.shields.io/badge/DRF-3.16.1-red)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-336791?logo=postgresql)
![Celery](https://img.shields.io/badge/Celery-Redis-37814A?logo=celery)
![LangChain](https://img.shields.io/badge/LangChain-AI%20%26%20RAG-white?logo=chainlink)
![License](https://img.shields.io/badge/License-Apache%202.0-yellow)

---

## ✨ Features

### 🧠 AI-Powered Maintenance Assistant
- **Smart Task Catalog Generation:** Automatically synthesizes periodic maintenance plans tailored to vehicle make, model, year, displacement, and riding/driving conditions, combined with community knowledge.
- **Document RAG with pgvector:** Upload workshop manuals or technical specification sheets (PDF/images). WrenchBuddy extracts text, generates vector embeddings (768 dimensions), and stores them using `pgvector` for accurate technical retrieval.
- **Invoice & Receipt OCR / Vision:** Upload photos or PDF invoices of shop visits. AI vision and text models extract labor, replaced parts, and costs automatically.
- **Vehicle-Contextual AI Chat:** Conversational assistant built with LangChain, fully injected with the vehicle's real specs, computed maintenance schedule, service history, accessories, and RAG document context in the user's preferred language (English or Spanish).

### 📊 Service History & Cost Tracking
- **Maintenance Events:** Log detailed maintenance records with date, odometer reading, costs, notes, and invoice attachments.
- **Modifications & Accessories:** Keep track of aftermarket parts, accessories, and their purchase costs.
- **PDF Report Generation:** Export comprehensive vehicle history and condition reports as downloadable PDFs using ReportLab.
- **Expense Analytics:** Monitor total spend and maintenance frequency with configurable privacy settings (public/private).

### 🏍️ Digital Garage & Social Community
- **Digital Garage Showcase:** Public or private garage profiles showcasing vehicles and cover photo galleries.
- **Social Feed & Interactions:** Follow fellow enthusiasts, view an activity feed of recent updates, like vehicles or photos, and leave comments.

---

## 🛠️ Tech Stack

| Layer | Technologies |
|---|---|
| **Backend Framework** | Python 3.12, Django 6.0.2, Django REST Framework 3.16.1 |
| **Database** | PostgreSQL with `pgvector` extension |
| **Async Tasks & Queues** | Celery 5.4.0 + Redis 5.2.1 |
| **Object Storage (Media)** | AWS S3 / MinIO via `django-storages` and `boto3` |
| **AI & LLM Orchestration** | LangChain (`langchain-openai`), compatible with OpenAI / Leria / Ollama endpoints |
| **Document Processing & PDF** | ReportLab (PDF export), PyPDF2, Pillow |
| **Containerization** | Docker, Gunicorn |

---

## 📂 Project Structure

```text
WrenchBuddy/
├── wrench_buddy/          # Project configuration, settings, ASGI/WSGI, and root URLs
├── users/                 # Custom user model, authentication, profiles, and language preferences
├── vehicles/              # Vehicles CRUD, technical documents (RAG vector chunks), PDF report export
├── maintenance/           # Maintenance events, smart task catalogs, attachments, and accessories
├── ai_assistant/          # LangChain chains, prompts, Celery asynchronous tasks, and chat endpoints
├── social/                # Digital garage photos, social feed, follows, likes, and comments
├── media/                 # Local media storage (when S3 is disabled)
├── Dockerfile             # Production container definition with Gunicorn
└── requirements.txt       # Project dependencies
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.12+
- PostgreSQL with `pgvector` extension installed (`CREATE EXTENSION vector;`)
- Redis server (for Celery message broker)
- MinIO or AWS S3 bucket (optional, local storage used by default)

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/WrenchBuddy.git
cd WrenchBuddy
```

### 2. Set Up Virtual Environment
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Environment Variables
Create an `.env` file or export the required environment variables:
```env
# Database
DB_NAME=wrenchbuddy
DB_USER=wrenchbuddy
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432

# Celery & Redis
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Storage (MinIO or AWS S3)
USE_S3=false
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin123
AWS_STORAGE_BUCKET_NAME=wrenchbuddy-media
AWS_S3_ENDPOINT_URL=http://localhost:9000

# AI Provider (OpenAI-compatible)
AI_BASE_URL=https://your-ai-provider.com
AI_API_KEY=your_api_key
AI_TEXT_MODEL=your-text-model
AI_VISION_MODEL=your-vision-model
AI_EMBEDDING_MODEL=your-embedding-model
```

### 4. Database Migrations & Superuser
```bash
python manage.py migrate
python manage.py createsuperuser
```

### 5. Run the Application
Start the Django development server:
```bash
python manage.py runserver
```

Start the Celery worker in a separate terminal:
```bash
celery -A wrench_buddy worker -l info
```

---

## 🌐 API Overview

| Area | Method | Endpoint | Description |
|---|---|---|---|
| **Auth & Users** | `POST` | `/api/users/` | User registration |
| | `GET` | `/api/users/me/` | Current user profile |
| | `GET` | `/api/users/profile/<username>/` | Public user profile |
| **Vehicles** | `GET/POST` | `/api/vehicles/` | List and create vehicles |
| | `GET/PUT/DELETE` | `/api/vehicles/<id>/` | Retrieve, update, or delete vehicle |
| | `GET` | `/api/vehicles/<id>/report/` | Download complete vehicle PDF report |
| | `POST` | `/api/vehicles/documents/` | Upload workshop manuals/specs for RAG |
| **Maintenance** | `GET/POST` | `/api/maintenance/events/` | List or create maintenance events |
| | `GET/POST` | `/api/maintenance/catalog/` | Vehicle task catalog |
| | `POST` | `/api/maintenance/attachments/` | Upload invoices/photos for AI analysis |
| | `GET/POST` | `/api/maintenance/accessories/` | Track vehicle modifications and parts |
| **AI Assistant** | `POST` | `/api/ai/chat/<vehicle_id>/` | Conversational RAG assistant for vehicle |
| **Social** | `GET` | `/api/garage/` | Explore public garages |
| | `GET` | `/api/social/feed/` | Activity feed of followed users |
| | `POST` | `/api/social/follow/<username>/` | Follow or unfollow a user |
| | `POST` | `/api/social/vehicles/<id>/like/` | Like or unlike a vehicle |

---

## 🐳 Docker Deployment

You can build and run WrenchBuddy with Docker:

```bash
# Build the Docker image
docker build -t wrenchbuddy:latest .

# Run container
docker run -p 8000:8000 --env-file .env wrenchbuddy:latest
```

---

## 🧪 Testing

Run test suites using `pytest`:

```bash
# Run all tests
pytest

# Run tests for specific applications
pytest ai_assistant/
pytest vehicles/
pytest maintenance/
pytest users/
pytest social/
```

---

## 📄 License

This project is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for details.
