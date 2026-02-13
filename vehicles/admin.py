from django.contrib import admin

from .models import Vehicle


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ['brand', 'model', 'year', 'vehicle_type', 'current_km', 'user', 'created_at']
    list_filter = ['vehicle_type', 'usage_type', 'brand']
    search_fields = ['brand', 'model', 'user__email']
    ordering = ['-created_at']
    raw_id_fields = ['user']
