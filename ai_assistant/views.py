import logging

from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from ai_assistant.services import generate_recommendations
from maintenance.serializers import MaintenanceTaskSerializer
from vehicles.models import Vehicle

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def recommendation_view(request, vehicle_id):
    """Generate AI maintenance recommendations for a vehicle.

    POST /api/ai/recommendations/<vehicle_id>/
    """
    try:
        vehicle = Vehicle.objects.get(id=vehicle_id, user=request.user)
    except Vehicle.DoesNotExist:
        return JsonResponse({'error': 'Vehicle not found.'}, status=404)

    try:
        tasks = generate_recommendations(vehicle.id)
    except Exception:
        logger.exception("AI recommendation failed for vehicle %s", vehicle_id)
        return JsonResponse(
            {'error': 'AI service unavailable. Please try again later.'},
            status=503,
        )

    serializer = MaintenanceTaskSerializer(tasks, many=True)
    return JsonResponse({
        'count': len(tasks),
        'recommendations': serializer.data,
    })
