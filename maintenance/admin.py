from django.contrib import admin

from .models import TaskCatalog, MaintenanceEvent, EventAttachment


@admin.register(TaskCatalog)
class TaskCatalogAdmin(admin.ModelAdmin):
    list_display = ['task_code', 'name', 'vehicle', 'source', 'interval_km', 'interval_months', 'is_safety_critical']
    list_filter = ['source', 'is_safety_critical']
    search_fields = ['task_code', 'name', 'description', 'vehicle__brand', 'vehicle__model']
    ordering = ['vehicle', 'task_code']
    raw_id_fields = ['vehicle']


@admin.register(MaintenanceEvent)
class MaintenanceEventAdmin(admin.ModelAdmin):
    list_display = ['vehicle', 'task_code', 'date', 'km_at_service', 'cost', 'created_at']
    list_filter = ['task_code', 'date']
    search_fields = ['vehicle__brand', 'vehicle__model', 'task_code', 'notes']
    ordering = ['-date', '-created_at']
    raw_id_fields = ['vehicle']
    date_hierarchy = 'date'


@admin.register(EventAttachment)
class EventAttachmentAdmin(admin.ModelAdmin):
    list_display = ['original_filename', 'file_type', 'event', 'uploaded_at']
    list_filter = ['file_type']
    search_fields = ['original_filename']
    raw_id_fields = ['event']
