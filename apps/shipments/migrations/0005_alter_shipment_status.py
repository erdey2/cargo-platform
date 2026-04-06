from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shipments", "0004_shipment_road_distance_km"),
    ]

    operations = [
        migrations.AlterField(
            model_name="shipment",
            name="status",
            field=models.CharField(
                choices=[
                    ("created", "Created"),
                    ("matching", "Matching"),
                    ("assigned", "Assigned"),
                    ("driver_arriving", "Driver Arriving"),
                    ("in_transit", "In Transit"),
                    ("delivered", "Delivered"),
                    ("completed", "Completed"),
                    ("no_driver", "No Driver"),
                    ("cancelled", "Cancelled"),
                ],
                db_index=True,
                default="created",
                max_length=20,
            ),
        ),
    ]
