from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('shipments', '0012_shipmentproofdelivery_confirmation_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='ShipmentPODOTP',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('phone', models.CharField(max_length=30)),
                ('code', models.CharField(db_index=True, max_length=10)),
                ('expires_at', models.DateTimeField()),
                ('attempts', models.IntegerField(default=0)),
                ('used', models.BooleanField(db_index=True, default=False)),
                ('pod', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='otps', to='shipments.shipmentproofofdelivery')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]

