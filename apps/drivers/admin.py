from django.contrib import admin
from .models import DriverProfile, DriverDocument, DriverEarning

admin.site.register(DriverProfile)
admin.site.register(DriverDocument)
admin.site.register(DriverEarning)
