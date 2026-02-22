import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ai_assistant.services import get_whats_due
from vehicles.models import Vehicle

logger = logging.getLogger(__name__)


class WhatsDueView(APIView):
    """GET /api/ai/whats-due/<vehicle_id>/
    Returns an ordered list of maintenance tasks the AI recommends doing now.
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

        try:
            recommendations = get_whats_due(vehicle.id)
        except Exception:
            logger.exception("Error generating what's due for vehicle %s", vehicle_id)
            return Response(
                {'detail': 'Error al consultar la IA. Inténtalo de nuevo.'},
                status=502,
            )

        return Response(recommendations)
