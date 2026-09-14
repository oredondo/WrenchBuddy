from django.conf import settings
from django.db import models
from pgvector.django import VectorField


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
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'vehicles'
        verbose_name = 'Vehículo'
        verbose_name_plural = 'Vehículos'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.brand} {self.model} ({self.year})"


def vehicle_document_path(instance, filename):
    return f'vehicle_docs/user_{instance.vehicle.user_id}/vehicle_{instance.vehicle_id}/{filename}'


class VehicleDocument(models.Model):
    """Documents uploaded by the user that provide context to the AI (RAG)."""

    class FileType(models.TextChoices):
        PDF = 'pdf', 'PDF'
        IMAGE = 'image', 'Imagen'

    class ExtractionStatus(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        PROCESSING = 'processing', 'Procesando'
        COMPLETED = 'completed', 'Completado'
        FAILED = 'failed', 'Fallido'

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='documents',
    )
    file = models.FileField(upload_to=vehicle_document_path)
    file_type = models.CharField(max_length=10, choices=FileType.choices)
    original_filename = models.CharField(max_length=255)
    description = models.CharField(max_length=200, blank=True, help_text='Ej: Manual de usuario, Ficha técnica')
    extracted_text = models.TextField(blank=True)
    extraction_status = models.CharField(
        max_length=20,
        choices=ExtractionStatus.choices,
        default=ExtractionStatus.PENDING,
    )
    extraction_error = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'vehicle_documents'
        verbose_name = 'Documento del vehículo'
        verbose_name_plural = 'Documentos del vehículo'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.original_filename} ({self.vehicle})"


class DocumentChunk(models.Model):
    """A text chunk from a VehicleDocument with its vector embedding for RAG."""

    document = models.ForeignKey(
        VehicleDocument,
        on_delete=models.CASCADE,
        related_name='chunks',
    )
    chunk_index = models.PositiveIntegerField()
    text = models.TextField()
    embedding = VectorField(dimensions=768)

    class Meta:
        db_table = 'document_chunks'
        ordering = ['document', 'chunk_index']

    def __str__(self):
        return f"Chunk {self.chunk_index} of {self.document}"
