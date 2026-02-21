from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import TaskCatalog, MaintenanceEvent, EventAttachment
from .serializers import (
    TaskCatalogSerializer,
    MaintenanceEventSerializer,
    MaintenanceEventCreateSerializer,
    EventAttachmentSerializer,
)


class TaskCatalogViewSet(viewsets.ModelViewSet):
    """CRUD catalog of maintenance tasks per vehicle."""
    serializer_class = TaskCatalogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = TaskCatalog.objects.filter(vehicle__user=self.request.user)
        vehicle_id = self.request.query_params.get('vehicle')
        if vehicle_id:
            queryset = queryset.filter(vehicle_id=vehicle_id)
        return queryset

    def perform_create(self, serializer):
        serializer.save()


class MaintenanceEventViewSet(viewsets.ModelViewSet):
    """CRUD for maintenance events (completed maintenance)."""
    serializer_class = MaintenanceEventSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return MaintenanceEventCreateSerializer
        return MaintenanceEventSerializer

    def get_queryset(self):
        queryset = MaintenanceEvent.objects.filter(vehicle__user=self.request.user)
        vehicle_id = self.request.query_params.get('vehicle')
        if vehicle_id:
            queryset = queryset.filter(vehicle_id=vehicle_id)
        return queryset


class EventAttachmentViewSet(viewsets.ModelViewSet):
    """CRUD for event attachments (invoices, photos)."""
    serializer_class = EventAttachmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = EventAttachment.objects.filter(
            event__vehicle__user=self.request.user
        )
        event_id = self.request.query_params.get('event')
        if event_id:
            queryset = queryset.filter(event_id=event_id)
        return queryset

    def perform_create(self, serializer):
        instance = serializer.save()
        from ai_assistant.tasks import analyze_attachment
        analyze_attachment.delay(instance.id)
