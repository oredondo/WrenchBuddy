from rest_framework import serializers

from maintenance.models import MaintenanceEvent, Accessory
from vehicles.models import Vehicle
from .models import GaragePhoto, Follow, VehicleComment, GaragePhotoComment


class GaragePhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = GaragePhoto
        fields = ['id', 'vehicle', 'image', 'caption', 'description', 'is_public', 'is_cover', 'uploaded_at']
        read_only_fields = ['uploaded_at']

    def validate_vehicle(self, vehicle):
        if vehicle.user != self.context['request'].user:
            raise serializers.ValidationError("No tienes permiso sobre este vehículo.")
        return vehicle


# --- Serializers públicos de garaje ---

class PublicMaintenanceEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaintenanceEvent
        fields = ['id', 'task_code', 'date', 'km_at_service', 'notes', 'cost']


class PublicAccessorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Accessory
        fields = ['id', 'name', 'price', 'notes']


class PublicGaragePhotoSerializer(serializers.ModelSerializer):
    likes_count = serializers.IntegerField(source='likes.count', read_only=True)

    class Meta:
        model = GaragePhoto
        fields = ['id', 'image', 'caption', 'description', 'is_cover', 'uploaded_at', 'likes_count']


class PublicVehicleSerializer(serializers.ModelSerializer):
    garage_photos = serializers.SerializerMethodField()
    maintenance_events = serializers.SerializerMethodField()
    accessories = serializers.SerializerMethodField()
    likes_count = serializers.IntegerField(source='likes.count', read_only=True)
    comments_count = serializers.IntegerField(source='comments.count', read_only=True)

    class Meta:
        model = Vehicle
        fields = [
            'id', 'vehicle_type', 'brand', 'model', 'year',
            'current_km', 'displacement', 'usage_type', 'notes',
            'likes_count', 'comments_count', 'garage_photos', 'maintenance_events', 'accessories',
        ]

    def get_garage_photos(self, obj):
        photos = obj.garage_photos.filter(is_public=True)
        return PublicGaragePhotoSerializer(photos, many=True, context=self.context).data

    def get_maintenance_events(self, obj):
        events = obj.maintenance_events.filter(is_public=True).order_by('-date')
        return PublicMaintenanceEventSerializer(events, many=True).data

    def get_accessories(self, obj):
        return PublicAccessorySerializer(obj.accessories.order_by('name'), many=True).data


# --- Follow ---

class FollowSerializer(serializers.ModelSerializer):
    follower_username  = serializers.CharField(source='follower.username', read_only=True)
    following_username = serializers.CharField(source='following.username', read_only=True)

    class Meta:
        model = Follow
        fields = ['id', 'follower_username', 'following_username', 'created_at']
        read_only_fields = ['id', 'created_at']


# --- Comentarios ---

class VehicleCommentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = VehicleComment
        fields = ['id', 'username', 'vehicle', 'body', 'created_at', 'updated_at']
        read_only_fields = ['id', 'username', 'created_at', 'updated_at']

    def validate_vehicle(self, vehicle):
        if not vehicle.is_public:
            raise serializers.ValidationError("Este vehículo no es público.")
        return vehicle


class GaragePhotoCommentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = GaragePhotoComment
        fields = ['id', 'username', 'photo', 'body', 'created_at', 'updated_at']
        read_only_fields = ['id', 'username', 'created_at', 'updated_at']

    def validate_photo(self, photo):
        if not photo.is_public:
            raise serializers.ValidationError("Esta foto no es pública.")
        return photo


# --- Feed ---

class FeedVehicleSerializer(serializers.ModelSerializer):
    owner = serializers.CharField(source='user.username', read_only=True)
    preview_photo = serializers.SerializerMethodField()

    class Meta:
        model = Vehicle
        fields = ['id', 'owner', 'brand', 'model', 'year', 'current_km', 'preview_photo', 'created_at']

    def get_preview_photo(self, obj):
        photo = obj.garage_photos.filter(is_public=True).first()
        if photo:
            return PublicGaragePhotoSerializer(photo, context=self.context).data
        return None
