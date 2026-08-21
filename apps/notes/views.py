# apps/notes/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from .models import Note
from .serializers import (
    NoteCreateSerializer,
    NoteListSerializer,
    NoteDetailSerializer,
    NoteUpdateSerializer,
    NoteApprovalSerializer,
    NotePreviewSerializer,
    NoteStatusUpdateSerializer,
    NoteResubmitSerializer,
)
from .permissions import IsVerifiedTeacher, IsAdminOrEditor


# ============================================================================
# 1. NOTE PREVIEW VIEW - ONLY FOR VERIFIED TEACHERS
# ============================================================================

class NotePreviewView(APIView):
    """
    POST /api/v1/notes/preview/
    
    ✅ ONLY verified teachers can preview their notes.
    This is like GitHub's preview button - shows how the content will look.
    Preview does NOT save anything to database.
    
    Purpose: Teachers can see the formatted version before publishing.
    """
    permission_classes = [IsVerifiedTeacher]  # ✅ ONLY verified teachers

    @extend_schema(
        summary="Preview Note (Verified Teachers Only)",
        operation_id="notes_preview",
        description="Preview note content before saving (Like GitHub preview). Only verified teachers can preview.",
        request=NotePreviewSerializer,
        responses={
            200: OpenApiResponse(description="Preview generated successfully"),
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Only verified teachers can preview notes"),
        }
    )
    def post(self, request):
        serializer = NotePreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        preview_data = serializer.get_preview_data()
        
        return Response({
            'success': True,
            'preview': preview_data,
            'message': 'Note preview generated successfully.'
        }, status=status.HTTP_200_OK)


# ============================================================================
# 2. NOTE CREATE VIEW - ONLY FOR VERIFIED TEACHERS
# ============================================================================

class NoteCreateView(APIView):
    """
    POST /api/v1/notes/
    
    ✅ ONLY verified teachers can create notes.
    New notes go to PENDING status for review.
    """
    permission_classes = [IsVerifiedTeacher]  # ✅ ONLY verified teachers

    @extend_schema(
        summary="Create Note (Verified Teachers Only)",
        operation_id="notes_create",
        description="Create a new note. Only verified teachers can create notes.",
        request=NoteCreateSerializer,
        responses={
            201: NoteDetailSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Only verified teachers can create notes"),
        }
    )
    def post(self, request):
        serializer = NoteCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        note = serializer.save()
        
        return Response(
            NoteDetailSerializer(note).data,
            status=status.HTTP_201_CREATED
        )


# ============================================================================
# 3. NOTE LIST VIEW - FOR EVERYONE (DISPLAYING NOTES)
# ============================================================================

class NoteListView(APIView):
    """
    GET /api/v1/notes/
    
    ✅ Everyone can view published notes.
    This is the DISPLAY part - showing notes on the website.
    
    Different users see different notes:
        - Admin/Editor: All notes (for moderation)
        - Teachers: Own notes + All published notes
        - Students: Only published notes
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List Notes (Display)",
        operation_id="notes_list",
        description="Display notes on the website. Everyone can view published notes.",
        parameters=[
            OpenApiParameter(name='subject', description='Filter by subject ID', required=False, type=int),
            OpenApiParameter(name='chapter', description='Filter by chapter ID', required=False, type=int),
            OpenApiParameter(name='search', description='Search by title', required=False, type=str),
        ],
        responses={200: NoteListSerializer(many=True)}
    )
    def get(self, request):
        user = request.user
        
        # Admin/Editor: See ALL notes (for moderation)
        if user.role in ['admin', 'editor']:
            queryset = Note.objects.all()
        
        # Teacher: See their own notes + ALL published notes
        elif user.is_instructor:
            queryset = Note.objects.filter(
                Q(uploaded_by=user) | Q(status=Note.Status.PUBLISHED)
            )
        
        # Student: See ONLY published notes
        else:
            queryset = Note.objects.filter(status=Note.Status.PUBLISHED)
        
        # Apply filters
        subject = request.query_params.get('subject')
        chapter = request.query_params.get('chapter')
        search = request.query_params.get('search')
        
        if subject:
            queryset = queryset.filter(subject_id=subject)
        if chapter:
            queryset = queryset.filter(chapter_id=chapter)
        if search:
            queryset = queryset.filter(title__icontains=search)
        
        queryset = queryset.order_by('-created_at')
        serializer = NoteListSerializer(queryset, many=True)
        return Response(serializer.data)


# ============================================================================
# 4. NOTE DETAIL VIEW - FOR EVERYONE (DISPLAYING NOTES)
# ============================================================================

class NoteDetailView(APIView):
    """
    GET /api/v1/notes/{id}/
    
    ✅ Everyone can view published notes.
    This is the DISPLAY part - showing full note on the website.
    
    Different users have different access:
        - Admin/Editor: Any note
        - Teachers: Own notes + Published notes
        - Students: Only published notes
    """
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        return get_object_or_404(Note, pk=pk)

    def check_view_permission(self, request, note):
        user = request.user
        
        # Admin and Editor: Can view ALL notes
        if user.role in ['admin', 'editor']:
            return True
        
        # Teacher: Can view own notes + published notes
        if user.is_instructor:
            return note.uploaded_by == user or note.is_published()
        
        # Student: Can view ONLY published notes
        if user.is_student:
            return note.is_published()
        
        return False

    @extend_schema(
        summary="Get Note Details (Display)",
        operation_id="notes_retrieve",
        description="Display full note on the website. Everyone can view published notes.",
        responses={
            200: NoteDetailSerializer,
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Note not found"),
        }
    )
    def get(self, request, pk):
        note = self.get_object(pk)
        
        if not self.check_view_permission(request, note):
            return Response({
                'error': 'You do not have permission to view this note.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Increment view count for all users viewing published notes
        if note.is_published():
            note.increment_views()
        
        serializer = NoteDetailSerializer(note)
        return Response(serializer.data)


# ============================================================================
# 5. NOTE UPDATE VIEW - ONLY FOR VERIFIED TEACHER OWNERS
# ============================================================================

class NoteUpdateView(APIView):
    """
    PATCH /api/v1/notes/{id}/
    
    ✅ ONLY verified teachers who own the note can update it.
    Only DRAFT or PENDING notes can be updated.
    """
    permission_classes = [IsVerifiedTeacher]

    @extend_schema(
        summary="Update Note (Verified Teacher Owner Only)",
        operation_id="notes_update",
        description="Update a note. Only verified teachers who own the note can update.",
        request=NoteUpdateSerializer,
        responses={
            200: NoteDetailSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Only verified teacher owner can update"),
            404: OpenApiResponse(description="Note not found"),
        }
    )
    def patch(self, request, pk):
        note = get_object_or_404(Note, pk=pk)
        
        # Check ownership
        if note.uploaded_by != request.user:
            return Response({
                'error': 'Only the teacher who created this note can update it.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Only DRAFT or PENDING notes can be updated
        if not note.can_edit():
            return Response({
                'error': f'Notes in {note.status} status cannot be updated.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = NoteUpdateSerializer(
            note,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        updated_note = serializer.save()
        
        return Response(
            NoteDetailSerializer(updated_note).data,
            status=status.HTTP_200_OK
        )


# ============================================================================
# 6. NOTE DELETE VIEW - ADMIN OR VERIFIED TEACHER OWNER
# ============================================================================

class NoteDeleteView(APIView):
    """
    DELETE /api/v1/notes/{id}/
    
    ✅ Admin OR verified teacher who owns the note can delete.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Delete Note",
        operation_id="notes_delete",
        description="Delete a note. Admin OR verified teacher owner can delete.",
        responses={
            204: OpenApiResponse(description="Note deleted successfully"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Note not found"),
        }
    )
    def delete(self, request, pk):
        note = get_object_or_404(Note, pk=pk)
        
        # Admin can delete any note
        if request.user.role == 'admin':
            note.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        
        # Teacher must be verified and own the note
        if not IsVerifiedTeacher().has_permission(request, self):
            return Response({
                'error': 'Only verified teachers can delete their own notes.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        if note.uploaded_by != request.user:
            return Response({
                'error': 'You can only delete your own notes.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        note.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ============================================================================
# 7. NOTE STATUS UPDATE VIEW - ONLY FOR VERIFIED TEACHER OWNERS
# ============================================================================

class NoteStatusUpdateView(APIView):
    """
    PATCH /api/v1/notes/{id}/status/
    
    ✅ ONLY verified teachers who own the note can update status.
    Status flow: DRAFT → PENDING → PUBLISHED
    """
    permission_classes = [IsVerifiedTeacher]

    @extend_schema(
        summary="Update Note Status",
        operation_id="notes_status_update",
        description="Update note status. Only verified teacher owner can update.",
        request=NoteStatusUpdateSerializer,
        responses={
            200: NoteDetailSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Only verified teacher owner can update status"),
            404: OpenApiResponse(description="Note not found"),
        }
    )
    def patch(self, request, pk):
        note = get_object_or_404(Note, pk=pk)
        
        if note.uploaded_by != request.user:
            return Response({
                'error': 'Only the note owner can update status.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = NoteStatusUpdateSerializer(
            data=request.data,
            context={'instance': note}
        )
        serializer.is_valid(raise_exception=True)
        
        new_status = serializer.validated_data['status']
        note.status = new_status
        
        if new_status == Note.Status.PUBLISHED:
            note.published_at = timezone.now()
            teacher = request.user.teacher_profile
            teacher.content_count += 1
            teacher.save(update_fields=['content_count'])
        
        note.save()
        
        return Response(
            NoteDetailSerializer(note).data,
            status=status.HTTP_200_OK
        )


# ============================================================================
# 8. NOTE APPROVAL VIEW - EDITOR/ADMIN ONLY
# ============================================================================

class NoteApprovalView(APIView):
    """
    POST /api/v1/notes/{id}/approve/
    
    ✅ Editor or Admin can approve or reject a pending note.
    """
    permission_classes = [IsAdminOrEditor]

    @extend_schema(
        summary="Approve/Reject Note",
        operation_id="notes_approve",
        description="Approve or reject a note (Editor/Admin only)",
        request=NoteApprovalSerializer,
        responses={
            200: NoteDetailSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Note not found"),
        }
    )
    def post(self, request, pk):
        note = get_object_or_404(Note, pk=pk)
        
        if note.status != Note.Status.PENDING:
            return Response({
                'error': f'Note is already {note.status}. Only pending notes can be reviewed.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = NoteApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        if serializer.validated_data['status'] == 'approved':
            note.status = Note.Status.PUBLISHED
            note.approved_at = timezone.now()
            note.published_at = timezone.now()
            note.rejection_reason = ""
            note.rejection_feedback = ""
            note.rejected_by = None
            note.rejected_at = None
            message = 'Note approved and published successfully.'
            note.save()
            
            return Response({
                'message': message,
                'feedback': '',
                'note': NoteDetailSerializer(note).data
            }, status=status.HTTP_200_OK)
        
        else:
            rejection_reason = serializer.validated_data.get('rejection_reason', '')
            rejection_feedback = serializer.validated_data.get('rejection_feedback', '')
            
            note.reject(
                user=request.user,
                reason=rejection_reason,
                feedback=rejection_feedback
            )
            
            return Response({
                'message': 'Note rejected.',
                'feedback': rejection_feedback,
                'note': NoteDetailSerializer(note).data
            }, status=status.HTTP_200_OK)


# ============================================================================
# 9. NOTE RESUBMIT VIEW - ONLY FOR VERIFIED TEACHERS
# ============================================================================

class NoteResubmitView(APIView):
    """
    POST /api/v1/notes/{id}/resubmit/
    
    ✅ Verified teachers can resubmit rejected notes.
    Moves note from REJECTED back to PENDING.
    """
    permission_classes = [IsVerifiedTeacher]

    @extend_schema(
        summary="Resubmit Rejected Note",
        operation_id="notes_resubmit",
        description="Resubmit a rejected note for review (Verified Teachers only)",
        request=NoteResubmitSerializer,
        responses={
            200: NoteDetailSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Only verified teacher owner can resubmit"),
            404: OpenApiResponse(description="Note not found"),
        }
    )
    def post(self, request, pk):
        note = get_object_or_404(Note, pk=pk)
        
        if note.uploaded_by != request.user:
            return Response({
                'error': 'Only the teacher who created this note can resubmit it.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        if not note.is_rejected():
            return Response({
                'error': f'Only rejected notes can be resubmitted. Current status: {note.status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        note.resubmit()
        
        return Response({
            'message': 'Note resubmitted successfully for review.',
            'note': NoteDetailSerializer(note).data
        }, status=status.HTTP_200_OK)


# ============================================================================
# 10. NOTE REJECTION INFO VIEW
# ============================================================================

class NoteRejectInfoView(APIView):
    """
    GET /api/v1/notes/{id}/reject-info/
    
    Get rejection details for a rejected note.
    Teachers can view their own rejection info.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Rejection Information",
        operation_id="notes_reject_info",
        description="Get rejection reason and feedback for a rejected note",
        responses={
            200: OpenApiResponse(description="Rejection information"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Note not found"),
        }
    )
    def get(self, request, pk):
        note = get_object_or_404(Note, pk=pk)
        
        if note.uploaded_by != request.user and request.user.role not in ['admin', 'editor']:
            return Response({
                'error': 'You do not have permission to view this information.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        if not note.is_rejected():
            return Response({
                'message': 'This note has not been rejected.',
                'status': note.status
            }, status=status.HTTP_200_OK)
        
        return Response({
            'id': note.id,
            'title': note.title,
            'status': note.status,
            'rejection_reason': note.rejection_reason,
            'rejection_feedback': note.rejection_feedback,
            'rejected_by': note.rejected_by.get_full_name() if note.rejected_by else None,
            'rejected_at': note.rejected_at,
            'can_resubmit': note.can_resubmit(),
        }, status=status.HTTP_200_OK)