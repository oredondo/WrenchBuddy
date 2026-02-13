from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import TaskCatalog, MaintenanceEvent, MaintenanceTask
from .serializers import (
    TaskCatalogSerializer,
    MaintenanceEventSerializer,
    MaintenanceEventCreateSerializer,
    MaintenanceTaskSerializer,
    MaintenanceTaskCompleteSerializer,
)


class TaskCatalogViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only catalog of maintenance tasks."""
    queryset = TaskCatalog.objects.all()
    serializer_class = TaskCatalogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = TaskCatalog.objects.all()
        vehicle_type = self.request.query_params.get('vehicle_type')
        if vehicle_type:
            queryset = queryset.filter(vehicle_type=vehicle_type)
        return queryset


class MaintenanceEventViewSet(viewsets.ModelViewSet):
    """CRUD for maintenance events (completed maintenance)."""
    serializer_class = MaintenanceEventSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return MaintenanceEvent.objects.filter(vehicle__user=self.request.user)

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


class MaintenanceTaskViewSet(viewsets.ModelViewSet):
    """CRUD for maintenance tasks (AI suggestions)."""
    serializer_class = MaintenanceTaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = MaintenanceTask.objects.filter(vehicle__user=self.request.user)
        vehicle_id = self.request.query_params.get('vehicle')
        status_filter = self.request.query_params.get('status')
        if vehicle_id:
            queryset = queryset.filter(vehicle_id=vehicle_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Mark a task as completed and create a MaintenanceEvent."""
        task = self.get_object()
        serializer = MaintenanceTaskCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Create the maintenance event
        event = MaintenanceEvent.objects.create(
            vehicle=task.vehicle,
            task_code=task.task_code,
            date=serializer.validated_data['date'],
            km_at_service=serializer.validated_data['km_at_service'],
            notes=serializer.validated_data.get('notes', ''),
            cost=serializer.validated_data.get('cost'),
            created_from_task=task,
        )

        # Update the task
        task.status = MaintenanceTask.Status.COMPLETED
        task.completed_event = event
        task.save()

        return Response(
            MaintenanceTaskSerializer(task).data,
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'])
    def dismiss(self, request, pk=None):
        """Dismiss a task (mark as not needed)."""
        task = self.get_object()
        task.status = MaintenanceTask.Status.DISMISSED
        task.save()
        return Response(
            MaintenanceTaskSerializer(task).data,
            status=status.HTTP_200_OK
        )
