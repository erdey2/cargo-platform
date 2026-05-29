#!/usr/bin/env python
"""
Validation script to test proof_of_delivery API endpoint with Cloudinary.
This script tests the complete flow:
1. Create a test shipment and assignment
2. Upload proof_of_delivery via API
3. Verify it's stored on Cloudinary
"""

import os
import django
import json
from io import BytesIO
from PIL import Image

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
django.setup()

from django.test import Client
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from apps.shipments.models import Shipment
from apps.users.models import User
from apps.drivers.models import DriverProfile
from apps.assignment.models import Assignment
from apps.vehicles.models import Vehicle

def create_test_data():
    """Create test user, driver, vehicle, shipment, and assignment"""
    print("📝 Creating test data...")

    # Get or create a driver user
    driver_user, _ = User.objects.get_or_create(
        email='test_driver_pod@example.com',
        defaults={
            'first_name': 'Test',
            'last_name': 'Driver POD',
            'role': 'driver'
        }
    )

    # Get or create driver profile
    driver, _ = DriverProfile.objects.get_or_create(
        user=driver_user,
        defaults={
            'verification_status': 'verified',
            'is_available': True,
            'is_online': True,
        }
    )

    # Get or create vehicle
    vehicle, _ = Vehicle.objects.get_or_create(
        driver=driver,
        defaults={
            'plate_number': 'TEST123',
            'vehicle_type': 'van',
            'capacity_weight': 100.0,
            'capacity_volume': 10.0,
            'verification_status': True,
        }
    )

    # Get an unassigned shipment or use existing one
    shipment = Shipment.objects.filter(
        assignment__isnull=False,
        proof_of_delivery__isnull=True,
        status='assigned'
    ).first()

    if not shipment:
        print("  ⚠️  No suitable shipment found for testing")
        return None, None

    print(f"  ✓ Using Shipment ID: {shipment.id}")
    print(f"  ✓ Using Driver ID: {driver.id}")

    return shipment, driver_user

def get_auth_token(user):
    """Get JWT authentication token for user"""
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token)

def test_proof_upload(shipment, driver_user):
    """Test uploading proof_of_delivery via API"""
    print("\n🚀 Testing Proof of Delivery Upload via API...")

    # Get assignment
    assignment = shipment.assignment

    # Create test image
    img = Image.new('RGB', (300, 300), color='green')
    img_io = BytesIO()
    img.save(img_io, format='JPEG')
    img_io.seek(0)
    img_io.name = 'delivery_proof.jpg'

    # Prepare API client with authentication
    client = APIClient()
    token = get_auth_token(driver_user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    # Prepare request data
    data = {
        'status': 'delivered',
        'proof_of_delivery': img_io,
    }

    # Make API request
    url = f'/api/assignments/{assignment.id}/update-status/'
    response = client.post(url, data, format='multipart')

    print(f"  📍 Endpoint: POST {url}")
    print(f"  📊 Status Code: {response.status_code}")

    if response.status_code == 200:
        print("  ✓ API request successful!")
        resp_data = response.json()

        # Check if proof URL is in response
        if 'shipment' in resp_data and 'proof_of_delivery' in resp_data['shipment']:
            proof_url = resp_data['shipment']['proof_of_delivery']
            print(f"  ✓ Proof URL: {proof_url}")

            if 'cloudinary.com' in proof_url:
                print("  ✓✓ URL is from Cloudinary CDN - SUCCESS!")
                return True
            else:
                print("  ⚠️  URL is not from Cloudinary")
                return False
        else:
            print("  ⚠️  No proof_of_delivery in response")
            print(f"  Response: {json.dumps(resp_data, indent=2)}")
    else:
        print(f"  ✗ API request failed with status {response.status_code}")
        print(f"  Response: {response.text}")

    return False

def verify_in_database(shipment):
    """Verify proof_of_delivery is stored in database"""
    print("\n💾 Verifying in Database...")

    shipment.refresh_from_db()

    if shipment.proof_of_delivery:
        print(f"  ✓ Proof saved in DB: {shipment.proof_of_delivery.name}")
        url = shipment.proof_of_delivery.url
        print(f"  ✓ Proof URL: {url}")

        if 'cloudinary.com' in url:
            print("  ✓✓ Database stores Cloudinary URL - SUCCESS!")
            return True
    else:
        print("  ✗ No proof_of_delivery in database")

    return False

def main():
    """Run all tests"""
    print("=" * 70)
    print("CLOUDINARY PROOF OF DELIVERY VALIDATION TEST")
    print("=" * 70)

    shipment, driver_user = create_test_data()
    if not shipment:
        print("\n❌ Cannot proceed without test data")
        return False

    success = test_proof_upload(shipment, driver_user)
    if success:
        success = verify_in_database(shipment)

    print("\n" + "=" * 70)
    if success:
        print("✅ ALL TESTS PASSED - PROOF OF DELIVERY CLOUDINARY SETUP WORKS!")
    else:
        print("❌ TESTS FAILED - Check configuration")
    print("=" * 70)

    return success

if __name__ == '__main__':
    main()

