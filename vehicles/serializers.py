from rest_framework import serializers

from .models import Vehicle, VehicleDocument


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = [
            'id', 'vehicle_type', 'brand', 'model', 'year',
            'current_km', 'displacement', 'usage_type', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class VehicleListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""

    class Meta:
        model = Vehicle
        fields = ['id', 'vehicle_type', 'brand', 'model', 'year', 'current_km']


class VehicleDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleDocument
        fields = [
            'id', 'vehicle', 'file', 'file_type', 'original_filename',
            'description', 'extraction_status', 'uploaded_at',
        ]
        read_only_fields = ['id', 'file_type', 'original_filename', 'extraction_status', 'uploaded_at']

    def create(self, validated_data):
        file = validated_data['file']
        ext = file.name.rsplit('.', 1)[-1].lower()
        if ext == 'pdf':
            validated_data['file_type'] = VehicleDocument.FileType.PDF
        else:
            validated_data['file_type'] = VehicleDocument.FileType.IMAGE
        validated_data['original_filename'] = file.name
        return super().create(validated_data)
