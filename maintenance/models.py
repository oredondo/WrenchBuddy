from django.db import models

from vehicles.models import Vehicle


class TaskCatalog(models.Model):
    """Catalog of maintenance tasks by vehicle type."""

    class VehicleType(models.TextChoices):
        MOTORCYCLE = 'motorcycle', 'Motocicleta'
        CAR = 'car', 'Coche'

    task_code = models.CharField(max_length=50, primary_key=True)
    vehicle_type = models.CharField(max_length=20, choices=VehicleType.choices)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    default_interval_km = models.PositiveIntegerField(null=True, blank=True)
    default_interval_months = models.PositiveIntegerField(null=True, blank=True)
    is_safety_critical = models.BooleanField(default=False)

    class Meta:
        db_table = 'task_catalog'
        verbose_name = 'Tarea de catálogo'
        verbose_name_plural = 'Catálogo de tareas'

    def __str__(self):
        return f"{self.name} ({self.vehicle_type})"


class MaintenanceEvent(models.Model):
    """Records of completed maintenance - what the user registers."""

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='maintenance_events'
    )
    task_code = models.CharField(max_length=50)
    date = models.DateField()
    km_at_service = models.PositiveIntegerField()
    notes = models.TextField(blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_from_task = models.ForeignKey(
        'MaintenanceTask',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='completed_events'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'maintenance_events'
        verbose_name = 'Evento de mantenimiento'
        verbose_name_plural = 'Eventos de mantenimiento'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.task_code} - {self.vehicle} ({self.date})"


class MaintenanceTask(models.Model):
    """AI-suggested maintenance tasks - pending work."""

    class Priority(models.TextChoices):
        HIGH = 'high', 'Alta'
        MEDIUM = 'medium', 'Media'
        LOW = 'low', 'Baja'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        COMPLETED = 'completed', 'Completada'
        DISMISSED = 'dismissed', 'Descartada'

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='maintenance_tasks'
    )
    task_code = models.CharField(max_length=50)
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM
    )
    due_km = models.PositiveIntegerField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    explanation = models.TextField(blank=True)
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    completed_event = models.OneToOneField(
        MaintenanceEvent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='source_task'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'maintenance_tasks'
        verbose_name = 'Tarea de mantenimiento'
        verbose_name_plural = 'Tareas de mantenimiento'
        ordering = ['priority', 'due_date', 'due_km']

    def __str__(self):
        return f"{self.task_code} - {self.vehicle} ({self.status})"


def event_attachment_path(instance, filename):
    """Generate upload path: attachments/user_<id>/event_<id>/<filename>"""
    user_id = instance.event.vehicle.user_id
    return f'attachments/user_{user_id}/event_{instance.event_id}/{filename}'


class EventAttachment(models.Model):
    """Attachments (invoices, photos) linked to a MaintenanceEvent."""

    class FileType(models.TextChoices):
        PDF = 'pdf', 'PDF'
        IMAGE = 'image', 'Imagen'

    class AnalysisStatus(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        PROCESSING = 'processing', 'Procesando'
        COMPLETED = 'completed', 'Completado'
        FAILED = 'failed', 'Fallido'

    event = models.ForeignKey(
        MaintenanceEvent,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    file = models.FileField(upload_to=event_attachment_path)
    file_type = models.CharField(max_length=10, choices=FileType.choices)
    original_filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    analysis_status = models.CharField(
        max_length=20,
        choices=AnalysisStatus.choices,
        default=AnalysisStatus.PENDING,
    )
    analysis_result = models.TextField(blank=True, null=True)
    analysis_error = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'event_attachments'
        verbose_name = 'Adjunto de evento'
        verbose_name_plural = 'Adjuntos de eventos'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.original_filename} ({self.event})"
