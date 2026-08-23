# apps/notes/permissions.py
from rest_framework.permissions import BasePermission


class IsVerifiedTeacher(BasePermission):
    """
    Allow only verified teachers to perform actions.
    Checks:
    1. User is authenticated
    2. User has role 'instructor'
    3. User has a teacher profile
    4. Teacher profile status is 'verified'
    """
    
    message = "Only verified teachers can perform this action."
    
    def has_permission(self, request, view):
        user = request.user
        
        if not user.is_authenticated:
            return False
        
        if not user.is_instructor:
            return False
        
        if not hasattr(user, 'teacher_profile'):
            return False
        
        return user.teacher_profile.status == 'verified'


class IsAdminOrEditor(BasePermission):
    """Allow only Admin or Editor users"""
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role in ['admin', 'editor']
        )


class IsTeacherOwner(BasePermission):
    """Allow only the teacher who owns the note"""
    
    def has_object_permission(self, request, view, obj):
        return obj.uploaded_by == request.user


class IsAdminOrTeacherOwner(BasePermission):
    """Allow Admin or the teacher who owns the note"""
    
    def has_object_permission(self, request, view, obj):
        if request.user.role == 'admin':
            return True
        return obj.uploaded_by == request.user


# ✅ ADD THIS NEW PERMISSION CLASS
class IsVerifiedTeacherOrAdmin(BasePermission):
    """
    Allow only verified teachers or Admin to perform actions.
    Checks:
    1. User is authenticated
    2. User is either:
       a. Admin (has full access)
       b. Verified teacher (has teacher profile and is verified)
    """
    
    message = "Only verified teachers or Admin can perform this action."
    
    def has_permission(self, request, view):
        user = request.user
        
        if not user.is_authenticated:
            return False
        
        # ✅ Admin has full access
        if user.role == 'admin':
            return True
        
        if not user.is_instructor:
            return False
        
        if not hasattr(user, 'teacher_profile'):
            return False
        
        return user.teacher_profile.status == 'verified'