from django.conf import settings
from django.db import models


class Vehicle(models.Model):
    """Generic vehicle model - supports motorcycles and cars."""

    class VehicleType(models.TextChoices):
        MOTORCYCLE = 'motorcycle', 'Motocicleta'
        CAR = 'car', 'Coche'

    class UsageType(models.TextChoices):
        CITY = 'city', 'Ciudad'
        MIXED = 'mixed', 'Mixto'
        HIGHWAY = 'highway', 'Carretera'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='vehicles'
    )
    vehicle_type = models.CharField(
        max_length=20,
        choices=VehicleType.choices,
        default=VehicleType.MOTORCYCLE
    )
    brand = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    year = models.PositiveIntegerField()
    current_km = models.PositiveIntegerField()
    displacement = models.PositiveIntegerField(null=True, blank=True, help_text='Cilindrada en cc')
    usage_type = models.CharField(
        max_length=20,
        choices=UsageType.choices,
        default=UsageType.MIXED
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'vehicles'
        verbose_name = 'Vehículo'
        verbose_name_plural = 'Vehículos'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.brand} {self.model} ({self.year})"
