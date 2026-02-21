from django.db.models.signals import post_save
from django.dispatch import receiver

from vehicles.models import Vehicle


@receiver(post_save, sender=Vehicle)
def vehicle_created(sender, instance, created, **kwargs):
    if created:
        from ai_assistant.tasks import generate_vehicle_catalog
        generate_vehicle_catalog.delay(instance.id)
