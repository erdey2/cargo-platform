from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Q, F
from django.utils import timezone
from django.db import models as django_models
from .models import (
    CargoType,
    Shipment,
    ShipmentStatusHistory,
    ShipmentProofOfDelivery,
    ShipmentPODOTP,
    TwilioDeliveryReceipt,
)
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class CargoTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'requires_special_vehicle', 'fragile', 'hazardous']
    search_fields = ['name']


class ShipmentStatusInline(admin.TabularInline):
    model = ShipmentStatusHistory
    extra = 0
    readonly_fields = ['status', 'changed_by', 'created_at', 'notes']
    can_delete = False


class ShipmentProofOfDeliveryInline(admin.TabularInline):
    model = ShipmentProofOfDelivery
    extra = 0
    readonly_fields = ['image_sha256', 'gps_verified', 'is_duplicate', 'customer_confirmed', 'created_at']
    can_delete = False
    fields = ['photo', 'gps_verified', 'is_duplicate', 'customer_confirmed', 'created_at']


class ShipmentAdmin(admin.ModelAdmin):
    list_display = [
        'pk',
        'customer_display',
        'status_display',
        'pickup_address',
        'dropoff_address',
        'pod_status_display',
        'delivered_at',
    ]
    list_filter = [
        'status',
        'created_at',
        'delivered_at',
        ('proofs_of_delivery', admin.RelatedOnlyFieldListFilter),
    ]
    search_fields = ['pk', 'customer__email', 'pickup_address', 'dropoff_address']
    readonly_fields = ['created_at', 'updated_at', 'assigned_at', 'picked_up_at', 'delivered_at']

    fieldsets = (
        ('Shipment Info', {
            'fields': ('pk', 'customer', 'driver', 'status', 'created_at', 'updated_at')
        }),
        ('Pickup', {
            'fields': ('pickup_address', 'pickup_location')
        }),
        ('Dropoff', {
            'fields': ('dropoff_address', 'dropoff_location', 'recipient_name', 'recipient_phone', 'recipient_alternate_phone')
        }),
        ('Cargo', {
            'fields': ('cargo_type', 'description', 'weight', 'volume')
        }),
        ('Pricing', {
            'fields': ('estimated_price', 'final_price', 'is_paid', 'road_distance_km')
        }),
        ('Timeline', {
            'fields': ('assigned_at', 'picked_up_at', 'delivered_at')
        }),
    )

    inlines = [ShipmentStatusInline, ShipmentProofOfDeliveryInline]

    def customer_display(self, obj):
        return obj.customer.email if obj.customer else '-'
    customer_display.short_description = 'Customer'

    def status_display(self, obj):
        status_colors = {
            'created': '#999999',
            'matching': '#FFA500',
            'assigned': '#0066CC',
            'driver_arriving': '#6600CC',
            'in_transit': '#009900',
            'delivered': '#00CC00',
            'completed': '#003366',
            'no_driver': '#CC0000',
            'cancelled': '#FF0000',
        }
        color = status_colors.get(obj.status, '#999999')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = 'Status'

    def pod_status_display(self, obj):
        pod_count = obj.proofs_of_delivery.count()
        confirmed_count = obj.proofs_of_delivery.filter(customer_confirmed=True).count()
        if pod_count == 0:
            return format_html('<span style="color: #999;">No POD</span>')
        elif confirmed_count == pod_count:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ All Confirmed ({}/{})</span>',
                confirmed_count, pod_count
            )
        elif confirmed_count > 0:
            return format_html(
                '<span style="color: orange;">⚠ Partial ({}/{})</span>',
                confirmed_count, pod_count
            )
        else:
            return format_html(
                '<span style="color: red;">✗ Pending ({}/{})</span>',
                confirmed_count, pod_count
            )
    pod_status_display.short_description = 'POD Status'


class ShipmentProofOfDeliveryAdmin(admin.ModelAdmin):
    list_display = [
        'pk',
        'shipment_link',
        'gps_verified_display',
        'is_duplicate_display',
        'customer_confirmed_display',
        'confirmation_method_display',
        'created_at',
    ]
    list_filter = [
        'gps_verified',
        'is_duplicate',
        'customer_confirmed',
        'customer_confirmation_method',
        ('created_at', admin.DateFieldListFilter),
    ]
    search_fields = ['pk', 'shipment__pk', 'image_sha256']
    readonly_fields = [
        'image_sha256',
        'gps_location',
        'gps_distance_to_dropoff_meters',
        'gps_verified',
        'is_duplicate',
        'duplicate_of',
        'created_at',
        'updated_at',
        'otp_count_display',
    ]

    fieldsets = (
        ('Shipment', {
            'fields': ('shipment', 'uploaded_by')
        }),
        ('Photo & Hash', {
            'fields': ('photo', 'image_sha256')
        }),
        ('GPS Verification', {
            'fields': ('gps_location', 'gps_accuracy_meters', 'gps_verified', 'gps_distance_to_dropoff_meters')
        }),
        ('Duplicate Detection', {
            'fields': ('is_duplicate', 'duplicate_of')
        }),
        ('Customer Confirmation', {
            'fields': ('customer_confirmed', 'customer_confirmed_at', 'customer_confirmation_method', 'otp_count_display')
        }),
        ('Notes', {
            'fields': ('verification_notes', 'metadata')
        }),
        ('OTP Tracking', {
            'fields': ('otp_resend_count', 'last_otp_sent_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def shipment_link(self, obj):
        url = reverse('admin:shipments_shipment_change', args=[obj.shipment.pk])
        return format_html('<a href="{}">{}</a>', url, obj.shipment.pk)
    shipment_link.short_description = 'Shipment'

    def gps_verified_display(self, obj):
        if obj.gps_verified:
            return format_html('<span style="color: green;">✓ Verified</span>')
        else:
            return format_html('<span style="color: red;">✗ Not Verified</span>')
    gps_verified_display.short_description = 'GPS Verified'

    def is_duplicate_display(self, obj):
        if obj.is_duplicate:
            return format_html('<span style="color: orange;">⚠ Duplicate</span>')
        else:
            return format_html('<span style="color: green;">✓ Unique</span>')
    is_duplicate_display.short_description = 'Duplicate'

    def customer_confirmed_display(self, obj):
        if obj.customer_confirmed:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Confirmed</span>'
            )
        else:
            return format_html('<span style="color: orange;">⚠ Pending</span>')
    customer_confirmed_display.short_description = 'Customer Confirmed'

    def confirmation_method_display(self, obj):
        methods = {
            'otp': '📱 OTP',
            'in_app': '📲 In-App',
            '': '—'
        }
        method_text = methods.get(obj.customer_confirmation_method, obj.customer_confirmation_method)
        return format_html(method_text)
    confirmation_method_display.short_description = 'Confirmation Method'

    def otp_count_display(self, obj):
        otp_count = obj.otps.count()
        confirmed_otps = obj.otps.filter(used=True).count()
        return format_html(
            'Total: {} | Used: {} | Resends: {}',
            otp_count, confirmed_otps, obj.otp_resend_count
        )
    otp_count_display.short_description = 'OTP Summary'


class ShipmentPODOTPAdmin(admin.ModelAdmin):
    list_display = [
        'pk',
        'pod_link',
        'phone',
        'code',
        'status_display',
        'attempts',
        'expires_at_display',
        'created_at',
    ]
    list_filter = [
        'used',
        ('expires_at', admin.DateFieldListFilter),
        ('created_at', admin.DateFieldListFilter),
    ]
    search_fields = ['pk', 'pod__shipment__pk', 'phone', 'code']
    readonly_fields = [
        'pod',
        'code',
        'expires_at',
        'attempts',
        'used',
        'created_at',
        'updated_at',
        'delivery_status_display',
    ]

    fieldsets = (
        ('OTP', {
            'fields': ('pod', 'phone', 'code', 'expires_at')
        }),
        ('Status', {
            'fields': ('used', 'attempts')
        }),
        ('SMS Delivery', {
            'fields': ('delivery_status_display',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def pod_link(self, obj):
        url = reverse('admin:shipments_shipmentproofofdelivery_change', args=[obj.pod.pk])
        return format_html('<a href="{}">{}</a>', url, obj.pod.pk)
    pod_link.short_description = 'POD'

    def status_display(self, obj):
        if obj.used:
            return format_html('<span style="color: green; font-weight: bold;">✓ Used</span>')
        elif obj.expires_at < timezone.now():
            return format_html('<span style="color: red;">✗ Expired</span>')
        else:
            return format_html('<span style="color: orange;">⏳ Pending</span>')
    status_display.short_description = 'Status'

    def expires_at_display(self, obj):
        now = timezone.now()
        if obj.expires_at < now:
            return format_html(
                '<span style="color: red;">Expired {}</span>',
                (now - obj.expires_at).seconds // 60
            )
        else:
            return format_html(
                '{} min',
                (obj.expires_at - now).seconds // 60
            )
    expires_at_display.short_description = 'Expires In'

    def delivery_status_display(self, obj):
        receipts = obj.delivery_receipts.all().order_by('-created_at')
        if not receipts:
            return format_html('<span style="color: #999;">No delivery receipts</span>')

        html_parts = []
        for receipt in receipts[:3]:  # Show last 3 receipts
            status_colors = {
                'queued': '#FFA500',
                'sent': '#0066CC',
                'delivered': '#00CC00',
                'undelivered': '#FF6600',
                'failed': '#CC0000',
            }
            color = status_colors.get(receipt.status, '#999999')
            html_parts.append(
                format_html(
                    '<div style="margin: 3px 0;"><span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 2px; font-size: 11px;">{}</span></div>',
                    color, receipt.status.upper()
                )
            )

        return format_html(''.join(html_parts))
    delivery_status_display.short_description = 'Delivery Receipts'


class TwilioDeliveryReceiptAdmin(admin.ModelAdmin):
    list_display = [
        'pk',
        'otp_link',
        'message_sid_display',
        'status_display',
        'retry_status_display',
        'error_display',
        'created_at',
    ]
    list_filter = [
        'status',
        'eligible_for_retry',
        'retry_count',
        ('created_at', admin.DateFieldListFilter),
    ]
    search_fields = ['pk', 'message_sid', 'otp__pod__shipment__pk', 'error_code']
    readonly_fields = [
        'otp',
        'message_sid',
        'status',
        'error_code',
        'error_message',
        'retry_count',
        'last_retry_at',
        'eligible_for_retry',
        'raw_webhook_data',
        'created_at',
        'updated_at',
    ]

    fieldsets = (
        ('Message', {
            'fields': ('otp', 'message_sid', 'status')
        }),
        ('Error Info', {
            'fields': ('error_code', 'error_message')
        }),
        ('Retry Tracking', {
            'fields': ('retry_count', 'last_retry_at', 'eligible_for_retry')
        }),
        ('Webhook Data', {
            'fields': ('raw_webhook_data',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['mark_eligible_for_retry', 'mark_ineligible_for_retry']

    def otp_link(self, obj):
        url = reverse('admin:shipments_shipmentpodotp_change', args=[obj.otp.pk])
        return format_html('<a href="{}">{}</a>', url, obj.otp.pk)
    otp_link.short_description = 'OTP'

    def message_sid_display(self, obj):
        return obj.message_sid[:20] + '...' if len(obj.message_sid) > 20 else obj.message_sid
    message_sid_display.short_description = 'Message SID'

    def status_display(self, obj):
        status_colors = {
            'queued': '#FFA500',
            'sent': '#0066CC',
            'delivered': '#00CC00',
            'undelivered': '#FF6600',
            'failed': '#CC0000',
        }
        color = status_colors.get(obj.status, '#999999')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold;">{}</span>',
            color, obj.status.upper()
        )
    status_display.short_description = 'Status'

    def retry_status_display(self, obj):
        if not obj.eligible_for_retry:
            return format_html('<span style="color: red;">✗ Not Eligible</span>')
        elif obj.retry_count > 0:
            return format_html('<span style="color: orange;">Retry #{}</span>', obj.retry_count)
        else:
            return format_html('<span style="color: green;">✓ Eligible</span>')
    retry_status_display.short_description = 'Retry Status'

    def error_display(self, obj):
        if obj.error_code:
            return format_html(
                '<span style="color: red;">{} - {}</span>',
                obj.error_code, obj.error_message
            )
        return '-'
    error_display.short_description = 'Error'

    def mark_eligible_for_retry(self, request, queryset):
        updated = queryset.update(eligible_for_retry=True)
        self.message_user(request, f'{updated} receipts marked as eligible for retry.')
    mark_eligible_for_retry.short_description = 'Mark as eligible for retry'

    def mark_ineligible_for_retry(self, request, queryset):
        updated = queryset.update(eligible_for_retry=False)
        self.message_user(request, f'{updated} receipts marked as ineligible for retry.')
    mark_ineligible_for_retry.short_description = 'Mark as ineligible for retry'


@admin.register(admin.site.__class__)
class OTPMetricsDashboard(admin.AdminSite):
    """Admin dashboard with OTP metrics and analytics"""
    pass


# Register models
admin.site.register(CargoType, CargoTypeAdmin)
admin.site.register(Shipment, ShipmentAdmin)
admin.site.register(ShipmentStatusHistory, admin.ModelAdmin)
admin.site.register(ShipmentProofOfDelivery, ShipmentProofOfDeliveryAdmin)
admin.site.register(ShipmentPODOTP, ShipmentPODOTPAdmin)
admin.site.register(TwilioDeliveryReceipt, TwilioDeliveryReceiptAdmin)
