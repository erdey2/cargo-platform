# Generated migration for retry fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shipments', '0015_shipmentproofdelivery_otp_resend_count'),
    ]

    operations = [
        migrations.AddField(
            model_name='twiliodeliveryreceipt',
            name='retry_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='twiliodeliveryreceipt',
            name='last_retry_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='twiliodeliveryreceipt',
            name='eligible_for_retry',
            field=models.BooleanField(default=True, db_index=True),
        ),
    ]

