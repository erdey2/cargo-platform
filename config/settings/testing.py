from .base import *

SECRET_KEY = "django-insecure-testkey"
# Use temporary DB for CI tests
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "test_db",
        "USER": "postgres",
        "PASSWORD": "postgres",
        "HOST": "localhost",
        "PORT": "5432",
    }
}

# Disable sending real emails
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Use fake Cloudinary for tests
CLOUDINARY_STORAGE = {
    "CLOUD_NAME": "test",
    "API_KEY": "test",
    "API_SECRET": "test",
}

# Use a fixed secret key for CI
SECRET_KEY = "django-insecure-testkey"

# Disable debug
DEBUG = False
