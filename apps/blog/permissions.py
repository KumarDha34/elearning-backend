from rest_framework.permissions import BasePermission, SAFE_METHODS


class CanWriteBlog(BasePermission):
    message = "Only instructors, editors, or admins can write blog posts."

    def has_permission(self, request, view):
        u = request.user
        return (
            u.is_authenticated
            and u.is_active
            and (u.is_instructor or u.is_editor or u.is_admin)
        )


class CanModerateBlog(BasePermission):
    message = "Only editors or admins can moderate blog posts."

    def has_permission(self, request, view):
        u = request.user
        return u.is_authenticated and (u.is_editor or u.is_admin)


class IsBlogAuthorOrModerator(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if request.user.is_editor or request.user.is_admin:
            return True
        return obj.uploaded_by == request.user