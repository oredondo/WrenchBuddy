from rest_framework import serializers

from .models import TaskCatalog, MaintenanceEvent, MaintenanceTask, EventAttachment


class TaskCatalogSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskCatalog
        fields = [
            'task_code', 'vehicle_type', 'name', 'description',
            'default_interval_km', 'default_interval_months', 'is_safety_critical'
        ]


class MaintenanceEventSerializer(serializers.ModelSerializer):
    task_name = serializers.SerializerMethodField()

    class Meta:
        model = MaintenanceEvent
        fields = [
            'id', 'vehicle', 'task_code', 'task_name', 'date', 'km_at_service',
            'notes', 'cost', 'created_from_task', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'task_name']

    def get_task_name(self, obj):
        task = TaskCatalog.objects.filter(task_code=obj.task_code).first()
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


class MaintenanceTaskSerializer(serializers.ModelSerializer):
    task_name = serializers.SerializerMethodField()

    class Meta:
        model = MaintenanceTask
        fields = [
            'id', 'vehicle', 'task_code', 'task_name', 'priority',
            'due_km', 'due_date', 'explanation', 'estimated_cost',
            'status', 'completed_event', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'task_name']

    def get_task_name(self, obj):
        task = TaskCatalog.objects.filter(task_code=obj.task_code).first()
        return task.name if task else obj.task_code


class EventAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventAttachment
        fields = ['id', 'event', 'file', 'file_type', 'original_filename', 'uploaded_at']
        read_only_fields = ['id', 'file_type', 'original_filename', 'uploaded_at']

    def validate_file(self, value):
        # Validate file type
        allowed_types = ['application/pdf', 'image/png', 'image/jpeg', 'image/webp']
        if value.content_type not in allowed_types:
            raise serializers.ValidationError(
                "Tipo de archivo no permitido. Solo PDF, PNG, JPEG o WebP."
            )
        # Limit file size to 10MB
        max_size = 10 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError("El archivo no puede superar 10MB.")
        return value

    def create(self, validated_data):
        file = validated_data['file']
        # Determine file_type from content_type
        if file.content_type == 'application/pdf':
            validated_data['file_type'] = EventAttachment.FileType.PDF
        else:
            validated_data['file_type'] = EventAttachment.FileType.IMAGE
        validated_data['original_filename'] = file.name
        return super().create(validated_data)


class MaintenanceTaskCompleteSerializer(serializers.Serializer):
    """Serializer for marking a task as completed."""
    date = serializers.DateField()
    km_at_service = serializers.IntegerField(min_value=0)
    notes = serializers.CharField(required=False, allow_blank=True)
    cost = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
