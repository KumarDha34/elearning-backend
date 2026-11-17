from rest_framework.permissions import BasePermission


class CanWriteBlog(BasePermission):
    """
    Any authenticated, active user can write a blog post.
    Students, instructors, editors, admins — all allowed.
    """
    message = "Authentication required to write blog posts."

    def has_permission(self, request, view):
        u = request.user
        return u.is_authenticated and u.is_active

class CanReviewBlog(BasePermission):
    """
    Only editors or admins can review (approve/reject) blog posts.
    """
    message = "Only editors or admins can review blog posts."

    def has_permission(self, request, view):
        u = request.user
        return u.is_authenticated and (u.is_editor or u.is_admin)