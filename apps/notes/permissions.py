from rest_framework.permissions import BasePermission

class IsVerifiedTeacher(BasePermission):
    message = "Only verified teachers can perform this action."
    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated or not user.is_instructor: return False
        if not hasattr(user, 'teacher_profile'): return False
        return user.teacher_profile.status == 'verified'

class IsAdminOrEditor(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['admin', 'editor']

class IsVerifiedTeacherOrAdmin(BasePermission):
    message = "Only verified teachers or Admin can perform this action."
    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated: return False
        if user.role == 'admin': return True
        if not user.is_instructor or not hasattr(user, 'teacher_profile'): return False
        return user.teacher_profile.status == 'verified'

class IsAdminOrEditor(BasePermission):
    """
    Allows access only to users with the 'admin' or 'editor' role.
    """
    message = "Only Admins or Editors can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.role in ['admin', 'editor']
        )