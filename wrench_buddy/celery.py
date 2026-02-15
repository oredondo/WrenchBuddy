import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wrench_buddy.settings')

app = Celery('wrench_buddy')
app.config_from_object('django.conf:settings', namespace='CELERY')
# app.conf.task_always_eager = True
# app.conf.task_eager_propagates = True

app.autodiscover_tasks()

# Para probar en local, ejecutar worker desde WrenchBuddy/:
# celery -A wrench_buddy worker --loglevel=info
#
# Para lanzar una tarea manualmente desde el shell de Django:
# python manage.py shell
# >>> from ai_assistant.tasks import analyze_attachment
# >>> analyze_attachment.delay(1)  # donde 1 es el id del EventAttachment
