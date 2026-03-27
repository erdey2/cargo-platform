from django.contrib import admin
from .models import AuditLog, Dispute


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["id", "admin_user", "action", "target_model", "target_id", "created_at"]
    list_filter = ["action", "created_at"]
    search_fields = ["admin_user__email", "target_id", "details"]
    readonly_fields = ["admin_user", "action", "target_model", "target_id", "details", "ip_address", "created_at"]


@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = ["id", "shipment", "raised_by", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["subject", "description", "raised_by__email"]
