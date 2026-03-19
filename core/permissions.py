from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or request.user and request.user.is_staff


class IsDriver(BasePermission):
    def has_permission(self, request, view):
        return (
                request.user.is_authenticated and
                request.user.role == "driver"
        )
