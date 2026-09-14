from django.conf import settings
from django.db import models

from vehicles.models import Vehicle


def garage_photo_path(instance, filename):
    return f'garage/user_{instance.vehicle.user_id}/vehicle_{instance.vehicle_id}/{filename}'


class GaragePhoto(models.Model):
    vehicle     = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='garage_photos')
    image       = models.ImageField(upload_to=garage_photo_path)
    caption     = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    is_public   = models.BooleanField(default=True)
    is_cover    = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'garage_photos'
        ordering = ['-is_cover', '-uploaded_at']


class Follow(models.Model):
    follower  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='following')
    following = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='followers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'social_follows'
        unique_together = [('follower', 'following')]
        ordering = ['-created_at']


class VehicleLike(models.Model):
    user    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='vehicle_likes')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'social_vehicle_likes'
        unique_together = [('user', 'vehicle')]


class GaragePhotoLike(models.Model):
    user  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='photo_likes')
    photo = models.ForeignKey(GaragePhoto, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'social_photo_likes'
        unique_together = [('user', 'photo')]


class VehicleComment(models.Model):
    user    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='vehicle_comments')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='comments')
    body    = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'social_vehicle_comments'
        ordering = ['created_at']


class GaragePhotoComment(models.Model):
    user  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='photo_comments')
    photo = models.ForeignKey(GaragePhoto, on_delete=models.CASCADE, related_name='comments')
    body  = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'social_photo_comments'
        ordering = ['created_at']
