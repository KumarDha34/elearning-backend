from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin


class IsStudent(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_student


class IsInstructor(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_instructor


class IsEditor(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_editor

class IsVerifiedTeacher(BasePermission):
    """Permission for verified teachers only"""
    message = "Teacher account not verified. Please upload verification document and wait for approval."

    def has_permission(self, request, view):
        return (request.user.is_authenticated and 
                request.user.is_instructor and 
                request.user.is_verified_teacher)

class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_authenticated and request.user.is_admin


class IsAdminOrEditor(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_admin or request.user.is_editor
        )


class IsAdminOrInstructor(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_admin or request.user.is_instructor
        )


class IsActiveUser(BasePermission):
    message = "Account is deactivated."

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_active


class IsPhoneVerified(BasePermission):
    message = "Phone number not verified."

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.phone_verified


class HasCompletedProfile(BasePermission):
    message = "Profile not completed."

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.profile_completed


class IsOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        
        owner_attrs = ['user', 'owner', 'student', 'author', 'created_by']
        for attr in owner_attrs:
            if hasattr(obj, attr):
                owner = getattr(obj, attr)
                if owner and owner == request.user:
                    return True
        
        return False


class IsStudentWithProfile(BasePermission):
    def has_permission(self, request, view):
        return (request.user.is_authenticated and
                request.user.is_student and
                request.user.profile_completed and
                request.user.is_active)


class IsInstructorWithProfile(BasePermission):
    def has_permission(self, request, view):
        return (request.user.is_authenticated and
                request.user.is_instructor and
                request.user.profile_completed and
                request.user.is_active)
    
class IsVerifiedInstructorWithProfile(BasePermission):
    """For instructors who are verified and can perform operations"""
    def has_permission(self, request, view):
        return (request.user.is_authenticated and
                request.user.is_instructor and
                request.user.is_verified_teacher and
                request.user.profile_completed and
                request.user.is_active)