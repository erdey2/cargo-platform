from django.db import migrations


def forwards(apps, schema_editor):
    Assignment = apps.get_model('assignment', 'Assignment')
    Shipment = apps.get_model('shipments', 'Shipment')

    # For every assignment, if the shipment has no driver, set it from the assignment
    for a in Assignment.objects.select_related('shipment', 'driver').all():
        if a.shipment_id and a.driver_id:
            Shipment.objects.filter(pk=a.shipment_id, driver__isnull=True).update(driver_id=a.driver_id)


def reverse(apps, schema_editor):
    # No-op reverse: don't remove drivers
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('assignment', '0004_alter_assignment_status'),
        ('shipments', '0007_shipment_driver_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, reverse),
    ]

