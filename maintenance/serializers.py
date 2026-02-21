from rest_framework import serializers

from .models import TaskCatalog, MaintenanceEvent, EventAttachment


class TaskCatalogSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskCatalog
        fields = [
            'id', 'vehicle', 'task_code', 'name', 'description',
            'interval_km', 'interval_months', 'is_safety_critical',
            'source', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def validate_vehicle(self, value):
        user = self.context['request'].user
        if value.user != user:
            raise serializers.ValidationError("No tienes permiso para este vehículo.")
        return value


class MaintenanceEventSerializer(serializers.ModelSerializer):
    task_name = serializers.SerializerMethodField()

    class Meta:
        model = MaintenanceEvent
        fields = [
            'id', 'vehicle', 'task_code', 'task_name', 'date', 'km_at_service',
            'notes', 'cost', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'task_name']

    def get_task_name(self, obj):
        task = TaskCatalog.objects.filter(vehicle=obj.vehicle, task_code=obj.task_code).first()
        return task.name if task else obj.task_code


class MaintenanceEventCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaintenanceEvent
        fields = ['id', 'vehicle', 'task_code', 'date', 'km_at_service', 'notes', 'cost']
        read_only_fields = ['id']

    def validate_vehicle(self, value):
        user = self.context['request'].user
        if value.user != user:
            raise serializers.ValidationError("No tienes permiso para este vehículo.")
        return value


class EventAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventAttachment
        fields = [
            'id', 'event', 'file', 'file_type', 'original_filename', 'uploaded_at',
            'analysis_status', 'analysis_result',
        ]
        read_only_fields = [
            'id', 'file_type', 'original_filename', 'uploaded_at',
            'analysis_status', 'analysis_result',
        ]

    def validate_file(self, value):
        allowed_types = ['application/pdf', 'image/png', 'image/jpeg', 'image/webp']
        if value.content_type not in allowed_types:
            raise serializers.ValidationError(
                "Tipo de archivo no permitido. Solo PDF, PNG, JPEG o WebP."
            )
        max_size = 10 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError("El archivo no puede superar 10MB.")
        return value

    def create(self, validated_data):
        file = validated_data['file']
        if file.content_type == 'application/pdf':
            validated_data['file_type'] = EventAttachment.FileType.PDF
        else:
            validated_data['file_type'] = EventAttachment.FileType.IMAGE
        validated_data['original_filename'] = file.name
        return super().create(validated_data)
