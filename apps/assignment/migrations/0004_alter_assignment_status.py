from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("assignment", "0003_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="assignment",
            name="status",
            field=models.CharField(
                choices=[
                    ("assigned", "Assigned"),
                    ("driver_arriving", "Driver Arriving"),
                    ("in_transit", "In Transit"),
                    ("delivered", "Delivered"),
                    ("completed", "Completed"),
                    ("cancelled", "Cancelled"),
                ],
                db_index=True,
                default="assigned",
                max_length=20,
            ),
        ),
    ]
