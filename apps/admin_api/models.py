from django.db import models
from django.contrib.auth import get_user_model
from core.models import BaseModel

User = get_user_model()


class AuditLog(BaseModel):
    """Tracks admin actions for audit trail."""

    ACTION_CHOICES = [
        ("user_update", "User Update"),
        ("driver_verify", "Driver Verify"),
        ("driver_reject", "Driver Reject"),
        ("driver_suspend", "Driver Suspend"),
        ("driver_activate", "Driver Activate"),
        ("vehicle_verify", "Vehicle Verify"),
        ("vehicle_reject", "Vehicle Reject"),
        ("shipment_assign", "Shipment Assign"),
        ("shipment_cancel", "Shipment Cancel"),
        ("transaction_refund", "Transaction Refund"),
        ("dispute_resolve", "Dispute Resolve"),
        ("other", "Other"),
    ]

    admin_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, db_index=True)
    target_model = models.CharField(max_length=100, blank=True)  # e.g. "drivers.DriverProfile"
    target_id = models.CharField(max_length=50, blank=True)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.action} by {self.admin_user} at {self.created_at}"


class Dispute(BaseModel):
    """Dispute raised by customer or driver, resolved by admin."""

    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_review", "In Review"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
    ]

    shipment = models.ForeignKey(
        "shipments.Shipment",
        on_delete=models.CASCADE,
        related_name="disputes",
    )
    raised_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="raised_disputes",
    )
    subject = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="open",
        db_index=True,
    )
    resolution = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_disputes",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Dispute #{self.id} - {self.shipment_id}"
