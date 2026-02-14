from django.contrib import admin

from .models import TaskCatalog, MaintenanceEvent, MaintenanceTask, EventAttachment


@admin.register(TaskCatalog)
class TaskCatalogAdmin(admin.ModelAdmin):
    list_display = ['task_code', 'name', 'vehicle_type', 'default_interval_km', 'default_interval_months', 'is_safety_critical']
    list_filter = ['vehicle_type', 'is_safety_critical']
    search_fields = ['task_code', 'name', 'description']
    ordering = ['vehicle_type', 'task_code']


@admin.register(MaintenanceEvent)
class MaintenanceEventAdmin(admin.ModelAdmin):
    list_display = ['vehicle', 'task_code', 'date', 'km_at_service', 'cost', 'created_at']
    list_filter = ['task_code', 'date']
    search_fields = ['vehicle__brand', 'vehicle__model', 'task_code', 'notes']
    ordering = ['-date', '-created_at']
    raw_id_fields = ['vehicle', 'created_from_task']
    date_hierarchy = 'date'


@admin.register(MaintenanceTask)
class MaintenanceTaskAdmin(admin.ModelAdmin):
    list_display = ['vehicle', 'task_code', 'priority', 'status', 'due_km', 'due_date', 'created_at']
    list_filter = ['status', 'priority', 'task_code']
    search_fields = ['vehicle__brand', 'vehicle__model', 'task_code', 'explanation']
    ordering = ['status', 'priority', 'due_date']
    raw_id_fields = ['vehicle', 'completed_event']


@admin.register(EventAttachment)
class EventAttachmentAdmin(admin.ModelAdmin):
    list_display = ['original_filename', 'file_type', 'event', 'uploaded_at']
    list_filter = ['file_type']
    search_fields = ['original_filename']
    raw_id_fields = ['event']
