"""Base settings to build other settings files upon."""
from pathlib import Path
import os, environ, dj_database_url
from datetime import timedelta
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve(strict=True).parent.parent.parent

APPS_DIR = BASE_DIR / "cargo_platform"
env = environ.Env()

env.read_env(str(BASE_DIR / ".env"))

SECRET_KEY = env("DJANGO_SECRET_KEY")

# GENERAL
DEBUG = env.bool("DJANGO_DEBUG", False)
TIME_ZONE = "Africa/Addis_Ababa"
LANGUAGE_CODE = "en-us"

# from django.utils.translation import gettext_lazy as _
# LANGUAGES = [
#     ('en', _('English')),
#     ('fr-fr', _('French')),
#     ('pt-br', _('Portuguese')),
# ]
SITE_ID = 1
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [str(BASE_DIR / "locale")]

DATABASE_URL = env("DATABASE_URL", default=None)

if DATABASE_URL:
    # Production database (Render)
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            engine="django.contrib.gis.db.backends.postgis",
            conn_max_age=600,
        )
    }
else:
    # Local PostgreSQL + PostGIS
    DATABASES = {
        "default": {
            "ENGINE": "django.contrib.gis.db.backends.postgis",
            "NAME": env("DB_NAME"),
            "USER": env("DB_USER"),
            "PASSWORD": env("DB_PASSWORD"),
            "HOST": env("DB_HOST"),
            "PORT": env("DB_PORT"),
        }
    }

DATABASES["default"]["ATOMIC_REQUESTS"] = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# URLS
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# APPS
DJANGO_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.admin",
    "django.contrib.gis",
]
THIRD_PARTY_APPS = [
    "corsheaders",
    "rest_framework",
    'rest_framework.authtoken',
    'allauth.socialaccount.providers.google',
    'dj_rest_auth',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'dj_rest_auth.registration',
    "allauth",
    "allauth.account",
    "allauth.mfa",
    "allauth.socialaccount",
    "drf_spectacular",
    'rolepermissions',
    'channels',
    'anymail',
    'cloudinary',
    'cloudinary_storage',
    'templated_mail',
    "apps.notifications.apps.NotificationsConfig",
]

LOCAL_APPS = [
    # custom apps
    "apps.admin_api",
    "apps.assignment",
    "core",
    "apps.pricing",
    "apps.location",
    "apps.matching",
    "apps.payments",
    "apps.rating",
    "apps.shipments",
    "apps.tracking",
    "apps.users",
    "apps.vehicles",
    "apps.wallet",
    "apps.drivers.apps.DriversConfig",
]
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

INSTALLED_APPS += ["django_celery_beat"]

# AUTHENTICATION
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
AUTH_USER_MODEL = "users.User"
ROLEPERMISSIONS_MODULE = 'apps.users.roles.base_roles'
ROLEPERMISSIONS_REGISTER_ADMIN = True
LOGIN_REDIRECT_URL = "users:redirect"
LOGIN_URL = "account_login"

ACCOUNT_SIGNUP_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# PASSWORDS
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# MIDDLEWARE
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]
CORS_ALLOW_ALL_ORIGINS = False

ASGI_APPLICATION = "config.asgi.application"

REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
            "capacity": 1500,
            "expiry": 10,
            
        },
    },
}

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

REDIS_URL = os.environ.get("REDIS_URL", default="redis://localhost:6379/0")
# Celery
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL

CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Africa/Addis_Ababa'

CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

''' CELERY_BEAT_SCHEDULE = {
    "expire-offers-every-10-seconds": {
        "task": "apps.matching.tasks.expire_offers_task",
        "schedule": 10.0,
    },
} '''

# Cloudinary Config
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': env('CLOUDINARY_CLOUD_NAME', default=None),
    'API_KEY': env('CLOUDINARY_API_KEY', default=None),
    'API_SECRET': env('CLOUDINARY_API_SECRET', default=None),
    'SECURE': True,
    'UPLOAD_OPTIONS': {
        'resource_type': 'auto',
        'quality': 'auto',
        'fetch_format': 'auto',
        'max_file_size': 52428800,  # 50MB
    }
}

# Django 5.x STORAGES Configuration
STORAGES = {
    'default': {
        'BACKEND': 'cloudinary_storage.storage.MediaCloudinaryStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# Fallback for older code that uses DEFAULT_FILE_STORAGE
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

# STATIC
STATIC_ROOT = str(BASE_DIR / "staticfiles")
STATIC_URL = "/static/"
STATICFILES_DIRS = [str(APPS_DIR / "static")]
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

# MEDIA
MEDIA_ROOT = str(APPS_DIR / "media")
MEDIA_URL = "/media/"

# TEMPLATES
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, 'templates')],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# FIXTURES
FIXTURE_DIRS = (str(APPS_DIR / "fixtures"),)

# SECURITY
SESSION_COOKIE_HTTPONLY = True

CSRF_COOKIE_HTTPONLY = True

X_FRAME_OPTIONS = "DENY"

# EMAIL
EMAIL_BACKEND = "anymail.backends.brevo.EmailBackend"

ANYMAIL = {
    "BREVO_API_KEY": env("BREVO_API_KEY", default=None),
}

DEFAULT_FROM_EMAIL = "Cargo Platform <noreply@online-car-market.com>"
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# Django Admin URL.
ADMIN_URL = env("DJANGO_ADMIN_URL", default="admin/")
ADMINS = [("""Erdey Syoum""", "erdeysyoum@gmail.com")]
MANAGERS = ADMINS

DJANGO_ADMIN_FORCE_ALLAUTH = env.bool("DJANGO_ADMIN_FORCE_ALLAUTH", default=False)

REDIS_SSL = REDIS_URL.startswith("rediss://")

# django-allauth
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*", "first_name*", "last_name*"]
ACCOUNT_ALLOW_REGISTRATION = env.bool("DJANGO_ACCOUNT_ALLOW_REGISTRATION", True)

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    # your other DRF settings...
}
REST_USE_JWT = True

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
}

# dj-rest-auth
REST_AUTH = {
    "USE_JWT": True,
    "TOKEN_MODEL": None,
    'JWT_AUTH_COOKIE': 'access',
    'JWT_AUTH_REFRESH_COOKIE': 'refresh',
    "JWT_AUTH_HTTPONLY": False,
    'REGISTER_SERIALIZER': 'apps.users.api.serializers.CustomRegisterSerializer',
    'LOGIN_SERIALIZER': 'apps.users.api.serializers.CustomLoginSerializer',
    'SIGNUP_FIELDS': {
        'username': {'required': False},
    }
}

REST_AUTH_REGISTER_PERMISSION_CLASSES = [
    'rest_framework.permissions.AllowAny',
]


SPECTACULAR_SETTINGS = {
    'TITLE': 'Cargo Platform API',
    'DESCRIPTION': 'API for cargo owners, and drivers',
    'VERSION': '1.0.0',
}

INTERNAL_IPS = [
    "127.0.0.1",
]

GOOGLE_MAPS_API_KEY="AIzaSyB2aFXLMFYNhwHqpH5v_e1Zuh1KFk7xe3c"

print("REDIS_URL:", env("REDIS_URL"))