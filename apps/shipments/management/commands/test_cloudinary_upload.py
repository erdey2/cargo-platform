"""
Management command to test Cloudinary upload for proof_of_delivery.
"""
from io import BytesIO
from django.core.management.base import BaseCommand, CommandError
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.shipments.models import Shipment
from django.conf import settings


class Command(BaseCommand):
    help = 'Test Cloudinary upload configuration for proof_of_delivery'

    def add_arguments(self, parser):
        parser.add_argument(
            '--shipment-id',
            type=int,
            help='Shipment ID to test upload to',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Testing Cloudinary Configuration...'))
        self.stdout.write('')

        # Check Cloudinary settings
        cloudinary_storage = getattr(settings, 'CLOUDINARY_STORAGE', {})
        default_storage = getattr(settings, 'DEFAULT_FILE_STORAGE', 'N/A')

        self.stdout.write(f"DEFAULT_FILE_STORAGE: {default_storage}")
        self.stdout.write(f"CLOUDINARY_STORAGE config:")
        for key in ['CLOUD_NAME', 'API_KEY', 'API_SECRET', 'SECURE', 'UPLOAD_OPTIONS']:
            value = cloudinary_storage.get(key, 'NOT SET')
            if key == 'API_SECRET' and value != 'NOT SET':
                value = '***HIDDEN***'
            self.stdout.write(f"  {key}: {value}")
        self.stdout.write('')

        # Check if credentials are set
        cloud_name = cloudinary_storage.get('CLOUD_NAME')
        api_key = cloudinary_storage.get('API_KEY')
        api_secret = cloudinary_storage.get('API_SECRET')

        if not all([cloud_name, api_key, api_secret]):
            raise CommandError(
                'Cloudinary credentials not fully configured in settings. '
                'Please set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET in .env'
            )

        self.stdout.write(self.style.SUCCESS('✓ Cloudinary credentials found'))
        self.stdout.write('')

        # Try to upload a test file
        self.stdout.write('Creating test image...')
        test_image = SimpleUploadedFile(
            name='test_proof_of_delivery.jpg',
            content=BytesIO(b'\xff\xd8\xff\xe0\x00\x10JFIF').getvalue(),
            content_type='image/jpeg'
        )

        shipment_id = options.get('shipment_id')
        if shipment_id:
            try:
                shipment = Shipment.objects.get(id=shipment_id)
                self.stdout.write(f'Testing upload to Shipment {shipment_id}...')

                # Save the proof of delivery
                shipment.proof_of_delivery = test_image
                shipment.save(update_fields=['proof_of_delivery'])

                self.stdout.write(self.style.SUCCESS('✓ File uploaded successfully to Cloudinary'))
                self.stdout.write('')
                self.stdout.write(f"Proof of Delivery URL: {shipment.proof_of_delivery.url}")
                self.stdout.write(f"Proof of Delivery Name: {shipment.proof_of_delivery.name}")

            except Shipment.DoesNotExist:
                raise CommandError(f'Shipment with ID {shipment_id} not found')
        else:
            # Just test storage without saving to a shipment
            from django.core.files.storage import default_storage
            self.stdout.write('Testing direct storage upload...')

            storage = default_storage
            self.stdout.write(f'Storage backend: {storage.__class__.__name__}')

            # Try to save a test file
            filename = storage.save('shipment_proofs/test_proof.jpg', test_image)
            self.stdout.write(self.style.SUCCESS(f'✓ File saved as: {filename}'))

            # Get the URL
            url = storage.url(filename)
            self.stdout.write(f'File URL: {url}')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('All tests passed! Cloudinary is properly configured for proof_of_delivery uploads.'))

