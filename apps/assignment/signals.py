from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Assignment


@receiver(post_save, sender=Assignment)
def ensure_shipment_driver(sender, instance, created, **kwargs):
    """Ensure the related Shipment.driver matches the Assignment.driver.

    This is defensive: some code paths may create an Assignment without updating
    the Shipment.driver. On save, if the shipment has no driver, update it.
    """
    shipment = instance.shipment
    # If shipment already has a driver and it's the same, nothing to do
    if shipment.driver_id == instance.driver_id:
        return

    # Only set driver when shipment has no driver to avoid overriding intentional changes
    if shipment.driver_id is None:
        # Use queryset update to avoid recursion and extra signals
        shipment.__class__.objects.filter(pk=shipment.pk, driver__isnull=True).update(driver=instance.driver)

