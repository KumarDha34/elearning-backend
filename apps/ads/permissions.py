# apps/ads/permissions.py

from rest_framework.permissions import BasePermission


class IsAdAdmin(BasePermission):
    """
    Custom permission to only allow users with the 'admin' role 
    (or superusers) to manage ad campaigns.
    """
    message = "You must be an administrator to manage ad campaigns."

    def has_permission(self, request, view):
        return bool(
            request.user 
            and request.user.is_authenticated 
            and (request.user.is_superuser or request.user.role == 'admin')
        )