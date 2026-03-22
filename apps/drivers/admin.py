from django.contrib import admin
from .models import DriverProfile, DriverDocument, DriverEarning

admin.register(DriverProfile, DriverDocument, DriverEarning)
