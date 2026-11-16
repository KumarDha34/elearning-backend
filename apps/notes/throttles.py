from rest_framework.throttling import BaseThrottle
from rest_framework.exceptions import Throttled
from django.utils import timezone
from datetime import timedelta
from .models import Note

class TeacherWeeklyUploadThrottle(BaseThrottle):
    """
    Limits teachers to uploading `content_limit` notes per 7 days.
    Default limit is 6 (from TeacherProfile).
    """
    def allow_request(self, request, view):
        # Only throttle instructors
        if not request.user.is_authenticated or request.user.role != 'instructor':
            return True

        if not hasattr(request.user, 'teacher_profile'):
            return True

        teacher = request.user.teacher_profile

        # 1. Check total lifetime limit (optional, if you want to keep content_count working)
        # if teacher.content_count >= teacher.content_limit:
        #     raise Throttled(detail="Total content limit reached.")

        # 2. Check weekly rate limit (Last 7 days)
        seven_days_ago = timezone.now() - timedelta(days=7)
        weekly_uploads = Note.objects.filter(
            uploaded_by=request.user,
            created_at__gte=seven_days_ago
        ).count()

        if weekly_uploads >= teacher.content_limit:
            raise Throttled(
                detail=f"Weekly upload limit reached. You can upload a maximum of {teacher.content_limit} notes per week."
            )
            
        return True

    def wait(self):
        return None