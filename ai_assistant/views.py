import logging

from celery.result import AsyncResult
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ai_assistant.tasks import compute_whats_due
from vehicles.models import Vehicle

logger = logging.getLogger(__name__)


class WhatsDueView(APIView):
    """GET /api/ai/whats-due/<vehicle_id>/
    Triggers a Celery task and returns the task_id for polling.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, vehicle_id):
        try:
            vehicle = Vehicle.objects.get(id=vehicle_id, user=request.user)
        except Vehicle.DoesNotExist:
            return Response({'detail': 'Vehículo no encontrado.'}, status=404)

        if not vehicle.task_catalog.exists():
            return Response(
                {'detail': 'El vehículo no tiene tareas de mantenimiento definidas.'},
                status=400,
            )

        task = compute_whats_due.delay(vehicle_id)
        return Response({'task_id': task.id, 'status': 'pending'}, status=202)


class WhatsDuePollView(APIView):
    """GET /api/ai/whats-due/<vehicle_id>/poll/<task_id>/
    Polls the Celery task result.
    Returns {"status": "pending"} while running,
    {"status": "ready", "result": [...]} when done,
    or {"status": "failed", "detail": "..."} on error.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, vehicle_id, task_id):
        # Verify the vehicle belongs to the user
        if not Vehicle.objects.filter(id=vehicle_id, user=request.user).exists():
            return Response({'detail': 'Vehículo no encontrado.'}, status=404)

        result = AsyncResult(task_id)

        if not result.ready():
            return Response({'status': 'pending'})

        if result.successful():
            return Response({'status': 'ready', 'result': result.get()})

        logger.error("compute_whats_due task %s failed: %s", task_id, result.result)
        return Response(
            {'status': 'failed', 'detail': 'Error al consultar la IA. Inténtalo de nuevo.'},
            status=502,
        )
