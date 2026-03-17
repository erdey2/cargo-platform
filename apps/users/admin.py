from rolepermissions.admin import RolePermissionsUserAdmin
from django.contrib import admin
from .models import User


class CustomRolePermissionsUserAdmin(RolePermissionsUserAdmin):
    ordering = ('email',)  # FIX HERE


admin.site.unregister(User)
admin.site.register(User, CustomRolePermissionsUserAdmin)
