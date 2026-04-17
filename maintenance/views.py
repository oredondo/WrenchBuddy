from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import TaskCatalog, MaintenanceEvent, EventAttachment, Accessory
from .serializers import (
    TaskCatalogSerializer,
    MaintenanceEventSerializer,
    MaintenanceEventCreateSerializer,
    EventAttachmentSerializer,
    AccessorySerializer,
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

    def perform_create(self, serializer):
        import re
        event = serializer.save()
        task_code = event.task_code
        if not task_code or task_code == 'pending_analysis':
            return
        in_catalog = TaskCatalog.objects.filter(
            vehicle=event.vehicle, task_code=task_code
        ).exists()
        if in_catalog:
            return
        # Already normalized (lowercase ASCII snake_case) → add to catalog directly
        if re.fullmatch(r'[a-z][a-z0-9_]*', task_code):
            TaskCatalog.objects.get_or_create(
                vehicle=event.vehicle,
                task_code=task_code,
                defaults={
                    'name': task_code.replace('_', ' ').title(),
                    'source': TaskCatalog.Source.USER_CREATED,
                },
            )
        else:
            # Free text / non-normalized → let AI translate and normalize
            from ai_assistant.tasks import normalize_task_code
            normalize_task_code.delay(event.id)


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


class AccessoryViewSet(viewsets.ModelViewSet):
    """CRUD for vehicle accessories and modifications."""
    serializer_class = AccessorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Accessory.objects.filter(vehicle__user=self.request.user)
        vehicle_id = self.request.query_params.get('vehicle')
        if vehicle_id:
            queryset = queryset.filter(vehicle_id=vehicle_id)
        return queryset
