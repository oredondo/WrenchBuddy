from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from vehicles.models import Vehicle
from .models import (
    GaragePhoto, Follow,
    VehicleLike, GaragePhotoLike,
    VehicleComment, GaragePhotoComment,
)
from .serializers import (
    GaragePhotoSerializer,
    PublicGaragePhotoSerializer,
    PublicVehicleSerializer,
    FollowSerializer,
    VehicleCommentSerializer,
    GaragePhotoCommentSerializer,
    FeedVehicleSerializer,
)
from .permissions import IsOwnerOrPublicReadOnly

User = get_user_model()


class GaragePhotoViewSet(viewsets.ModelViewSet):
    serializer_class = GaragePhotoSerializer

    def get_permissions(self):
        return [permissions.IsAuthenticated(), IsOwnerOrPublicReadOnly()]

    def get_queryset(self):
        qs = GaragePhoto.objects.select_related('vehicle__user')
        vehicle_id = self.request.query_params.get('vehicle')
        if vehicle_id:
            qs = qs.filter(vehicle_id=vehicle_id)
        if not self.request.user.is_authenticated:
            return qs.filter(is_public=True)
        return qs.filter(vehicle__user=self.request.user) | qs.filter(is_public=True)

    def perform_create(self, serializer):
        photo = serializer.save()
        if photo.is_cover:
            GaragePhoto.objects.filter(vehicle=photo.vehicle, is_cover=True).exclude(pk=photo.pk).update(is_cover=False)

    def perform_update(self, serializer):
        if serializer.instance.vehicle.user != self.request.user:
            raise PermissionDenied
        photo = serializer.save()
        if photo.is_cover:
            GaragePhoto.objects.filter(vehicle=photo.vehicle, is_cover=True).exclude(pk=photo.pk).update(is_cover=False)

    def perform_destroy(self, instance):
        if instance.vehicle.user != self.request.user:
            raise PermissionDenied
        was_cover = instance.is_cover
        vehicle = instance.vehicle
        instance.image.delete(save=False)
        instance.delete()
        if was_cover:
            first = GaragePhoto.objects.filter(vehicle=vehicle).first()
            if first:
                first.is_cover = True
                first.save(update_fields=['is_cover'])


# --- Garage público ---

class GarageListView(APIView):
    """GET /api/garage/ — lista de garajes públicos."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        users = (
            User.objects
            .filter(vehicles__is_public=True)
            .annotate(vehicle_count=Count('vehicles', filter=Q(vehicles__is_public=True)))
            .distinct()
        )
        data = []
        for user in users:
            preview = (
                GaragePhoto.objects
                .filter(vehicle__user=user, is_public=True)
                .select_related('vehicle')
                .first()
            )
            preview_data = (
                PublicGaragePhotoSerializer(preview, context={'request': request}).data
                if preview else None
            )
            data.append({
                'username': user.username,
                'vehicle_count': user.vehicle_count,
                'preview_photo': preview_data,
            })
        return Response(data)


class GarageDetailView(APIView):
    """GET /api/garage/<username>/ — garaje público de un usuario."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, username):
        user = User.objects.filter(username=username).first()
        if not user:
            raise NotFound("Usuario no encontrado.")
        vehicles = (
            Vehicle.objects
            .filter(user=user, is_public=True)
            .prefetch_related('garage_photos', 'maintenance_events', 'likes', 'comments')
        )
        from users.serializers import PublicUserSerializer
        serializer = PublicVehicleSerializer(vehicles, many=True, context={'request': request})
        profile = PublicUserSerializer(user, context={'request': request}).data
        return Response({
            'username': user.username,
            'profile': profile,
            'vehicles': serializer.data,
        })


# --- Follow ---

class FollowView(APIView):
    """POST /api/social/follow/<username>/ — seguir usuario."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, username):
        target = User.objects.filter(username=username).first()
        if not target:
            raise NotFound("Usuario no encontrado.")
        if target == request.user:
            raise ValidationError("No puedes seguirte a ti mismo.")
        _, created = Follow.objects.get_or_create(follower=request.user, following=target)
        return Response(
            {'detail': f'Siguiendo a {username}'},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request, username):
        target = User.objects.filter(username=username).first()
        if not target:
            raise NotFound("Usuario no encontrado.")
        Follow.objects.filter(follower=request.user, following=target).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FollowersView(APIView):
    """GET /api/social/followers/<username>/ — lista de seguidores."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, username):
        user = User.objects.filter(username=username).first()
        if not user:
            raise NotFound("Usuario no encontrado.")
        follows = Follow.objects.filter(following=user).select_related('follower')
        return Response([f.follower.username for f in follows])


class FollowingView(APIView):
    """GET /api/social/following/<username>/ — lista de seguidos."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, username):
        user = User.objects.filter(username=username).first()
        if not user:
            raise NotFound("Usuario no encontrado.")
        follows = Follow.objects.filter(follower=user).select_related('following')
        return Response([f.following.username for f in follows])


# --- Feed ---

class FeedView(APIView):
    """GET /api/social/feed/ — vehículos públicos de usuarios seguidos."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        following_ids = Follow.objects.filter(
            follower=request.user
        ).values_list('following_id', flat=True)
        vehicles = (
            Vehicle.objects
            .filter(user_id__in=following_ids, is_public=True)
            .select_related('user')
            .prefetch_related('garage_photos')
            .order_by('-created_at')
        )
        serializer = FeedVehicleSerializer(vehicles, many=True, context={'request': request})
        return Response(serializer.data)


# --- Likes ---

class VehicleLikeView(APIView):
    """POST/DELETE /api/social/vehicles/<id>/like/"""
    permission_classes = [permissions.IsAuthenticated]

    def _get_vehicle(self, pk):
        vehicle = Vehicle.objects.filter(pk=pk, is_public=True).first()
        if not vehicle:
            raise NotFound("Vehículo no encontrado o no es público.")
        return vehicle

    def post(self, request, pk):
        vehicle = self._get_vehicle(pk)
        _, created = VehicleLike.objects.get_or_create(user=request.user, vehicle=vehicle)
        return Response(
            {'likes': vehicle.likes.count()},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request, pk):
        vehicle = self._get_vehicle(pk)
        VehicleLike.objects.filter(user=request.user, vehicle=vehicle).delete()
        return Response({'likes': vehicle.likes.count()})


class GaragePhotoLikeView(APIView):
    """POST/DELETE /api/social/photos/<id>/like/"""
    permission_classes = [permissions.IsAuthenticated]

    def _get_photo(self, pk):
        photo = GaragePhoto.objects.filter(pk=pk, is_public=True).first()
        if not photo:
            raise NotFound("Foto no encontrada o no es pública.")
        return photo

    def post(self, request, pk):
        photo = self._get_photo(pk)
        _, created = GaragePhotoLike.objects.get_or_create(user=request.user, photo=photo)
        return Response(
            {'likes': photo.likes.count()},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request, pk):
        photo = self._get_photo(pk)
        GaragePhotoLike.objects.filter(user=request.user, photo=photo).delete()
        return Response({'likes': photo.likes.count()})


# --- Comentarios ---

class VehicleCommentViewSet(viewsets.ModelViewSet):
    serializer_class = VehicleCommentSerializer

    def get_permissions(self):
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        qs = VehicleComment.objects.select_related('user', 'vehicle')
        vehicle_id = self.request.query_params.get('vehicle')
        if vehicle_id:
            qs = qs.filter(vehicle_id=vehicle_id, vehicle__is_public=True)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.user != self.request.user:
            raise PermissionDenied
        serializer.save()

    def perform_destroy(self, instance):
        if instance.user != self.request.user:
            raise PermissionDenied
        instance.delete()


class GaragePhotoCommentViewSet(viewsets.ModelViewSet):
    serializer_class = GaragePhotoCommentSerializer

    def get_permissions(self):
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        qs = GaragePhotoComment.objects.select_related('user', 'photo')
        photo_id = self.request.query_params.get('photo')
        if photo_id:
            qs = qs.filter(photo_id=photo_id, photo__is_public=True)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.user != self.request.user:
            raise PermissionDenied
        serializer.save()

    def perform_destroy(self, instance):
        if instance.user != self.request.user:
            raise PermissionDenied
        instance.delete()
