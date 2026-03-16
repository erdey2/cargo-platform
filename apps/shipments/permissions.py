from rest_framework.permissions import BasePermission


class IsCustomer(BasePermission):

    def has_permission(self, request, view):
        return request.user.role == "customer"


class IsShipmentOwner(BasePermission):

    def has_object_permission(self, request, view, obj):
        return obj.customer == request.user