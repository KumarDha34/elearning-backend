from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated,AllowAny,IsAdminUser
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from .models import Note,OldQuestion
from .serializers import (
    NoteCreateSerializer,
    NoteListSerializer,
    NoteDetailSerializer,
    NoteUpdateSerializer,
    NoteApprovalSerializer,
    NotePreviewSerializer,
    NoteStatusUpdateSerializer,
    NoteResubmitSerializer,
    OldQuestionApprovalSerializer,
    OldQuestionCreateSerializer,
    OldQuestionListSerializer,
    OldQuestionDetailSerializer,
    OldQuestionUpdateSerializer,
    OldQuestionResubmitSerializer
)
from .permissions import (
    IsVerifiedTeacher,
    IsAdminOrEditor,
    IsVerifiedTeacherOrAdmin,  
)

# ============================================================================
# NOTE PREVIEW VIEW - VERIFIED TEACHERS OR ADMIN
# ============================================================================

class NotePreviewView(APIView):
    """
    POST /api/v1/notes/preview/
    
     Verified teachers or Admin can preview their notes.
    """
    permission_classes = [IsVerifiedTeacherOrAdmin] 

    @extend_schema(
        summary="Preview Note (Verified Teachers or Admin Only)",
        operation_id="notes_preview",
        description="Preview note content before saving. Only verified teachers or Admin can preview.",
        request=NotePreviewSerializer,
        responses={
            200: OpenApiResponse(description="Preview generated successfully"),
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
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
# NOTE CREATE VIEW - VERIFIED TEACHERS OR ADMIN
# ============================================================================

class NoteCreateView(APIView):
    """
    POST /api/v1/notes/
    
     Verified teachers or Admin can create notes.
    """
    permission_classes = [IsVerifiedTeacherOrAdmin] 

    @extend_schema(
        summary="Create Note (Verified Teachers or Admin Only)",
        operation_id="notes_create",
        description="Create a new note. Only verified teachers or Admin can create notes.",
        request=NoteCreateSerializer,
        responses={
            201: NoteDetailSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
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
# NOTE LIST VIEW - FOR EVERYONE
# ============================================================================

class NoteListView(APIView):
    """
    GET /api/v1/notes/
    
     Everyone can view published notes.
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
        
        if user.role in ['admin', 'editor']:
            queryset = Note.objects.all()
        elif user.is_instructor:
            queryset = Note.objects.filter(
                Q(uploaded_by=user) | Q(status=Note.Status.PUBLISHED)
            )
        else:
            queryset = Note.objects.filter(status=Note.Status.PUBLISHED)
        
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
# NOTE DETAIL VIEW - FOR EVERYONE
# ============================================================================

class NoteDetailView(APIView):
    """
    GET /api/v1/notes/{id}/
    
     Everyone can view published notes.
    """
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        return get_object_or_404(Note, pk=pk)

    def check_view_permission(self, request, note):
        user = request.user
        
        if user.role in ['admin', 'editor']:
            return True
        
        if user.is_instructor:
            return note.uploaded_by == user or note.is_published()
        
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
        
        if note.is_published():
            note.increment_views()
        
        serializer = NoteDetailSerializer(note)
        return Response(serializer.data)

# ============================================================================
# NOTE UPDATE VIEW - VERIFIED TEACHER OWNER OR ADMIN
# ============================================================================

class NoteUpdateView(APIView):
    """
    PATCH /api/v1/notes/{id}/
    
     Admin OR verified teacher who owns the note can update.
    """
    permission_classes = [IsAuthenticated] 

    @extend_schema(
        summary="Update Note (Admin or Verified Teacher Owner)",
        operation_id="notes_update",
        description="Update a note. Admin or verified teacher who owns the note can update.",
        request=NoteUpdateSerializer,
        responses={
            200: NoteDetailSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Note not found"),
        }
    )
    def patch(self, request, pk):
        note = get_object_or_404(Note, pk=pk)
        
        if request.user.role == 'admin':
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
        
        if not IsVerifiedTeacher().has_permission(request, self):
            return Response({
                'error': 'Only verified teachers can update their own notes.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        if note.uploaded_by != request.user:
            return Response({
                'error': 'Only the teacher who created this note can update it.'
            }, status=status.HTTP_403_FORBIDDEN)
        
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
# NOTE DELETE VIEW - ADMIN OR VERIFIED TEACHER OWNER
# ============================================================================

class NoteDeleteView(APIView):
    """
    DELETE /api/v1/notes/{id}/
    
     Admin OR verified teacher who owns the note can delete.
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
        
        if request.user.role == 'admin':
            note.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        
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
# NOTE STATUS UPDATE VIEW - VERIFIED TEACHER OWNER OR ADMIN
# ============================================================================

class NoteStatusUpdateView(APIView):
    """
    PATCH /api/v1/notes/{id}/status/
    
     Admin OR verified teacher who owns the note can update status.
    """
    permission_classes = [IsAuthenticated] 

    @extend_schema(
        summary="Update Note Status",
        operation_id="notes_status_update",
        description="Update note status. Admin or verified teacher owner can update.",
        request=NoteStatusUpdateSerializer,
        responses={
            200: NoteDetailSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Note not found"),
        }
    )
    def patch(self, request, pk):
        note = get_object_or_404(Note, pk=pk)
        
        # Admin can update any note
        if request.user.role == 'admin':
            serializer = NoteStatusUpdateSerializer(
                data=request.data,
                context={'instance': note}
            )
            serializer.is_valid(raise_exception=True)
            new_status = serializer.validated_data['status']
            note.status = new_status
            
            if new_status == Note.Status.PUBLISHED:
                note.published_at = timezone.now()
            
            note.save()
            return Response(
                NoteDetailSerializer(note).data,
                status=status.HTTP_200_OK
            )
        
        if not IsVerifiedTeacher().has_permission(request, self):
            return Response({
                'error': 'Only verified teachers can update their own notes.'
            }, status=status.HTTP_403_FORBIDDEN)
        
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
# NOTE APPROVAL VIEW - EDITOR/ADMIN ONLY
# ============================================================================

class NoteApprovalView(APIView):
    """
    POST /api/v1/notes/{id}/approve/
    
    Editor or Admin can approve or reject a pending note.
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
# NOTE RESUBMIT VIEW - VERIFIED TEACHER OR ADMIN
# ============================================================================

class NoteResubmitView(APIView):
    """
    POST /api/v1/notes/{id}/resubmit/
    
     Verified teachers or Admin can resubmit rejected notes.
    """
    permission_classes = [IsVerifiedTeacherOrAdmin] 

    @extend_schema(
        summary="Resubmit Rejected Note",
        operation_id="notes_resubmit",
        description="Resubmit a rejected note for review (Verified Teachers or Admin)",
        request=NoteResubmitSerializer,
        responses={
            200: NoteDetailSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Note not found"),
        }
    )
    def post(self, request, pk):
        note = get_object_or_404(Note, pk=pk)
        
        if note.uploaded_by != request.user and request.user.role != 'admin':
            return Response({
                'error': 'Only the teacher who created this note or Admin can resubmit it.'
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
# NOTE REJECTION INFO VIEW
# ============================================================================

class NoteRejectInfoView(APIView):
    """
    GET /api/v1/notes/{id}/reject-info/
    
    Get rejection details for a rejected note.
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

class OldQuestionCreateView(APIView):
    """
    POST /api/v1/notes/old-questions/create/
    
     Upload a past question paper
     Only verified teachers or Admin can upload
     Status automatically set to 'pending'
    """
    permission_classes = [IsVerifiedTeacherOrAdmin]

    @extend_schema(
        summary="Upload Old Question",
        operation_id="old_question_create",
        description="""
        Upload a past question paper.
        
        **Requirements:**
        - Only verified teachers or Admin can upload
        - Status automatically set to 'pending'
        - CKEditor content required (min 10 characters)
        
        **Workflow:**
        1. Teacher uploads → status = 'pending'
        2. Admin reviews and approves/rejects
        """,
        request=OldQuestionCreateSerializer,
        responses={
            201: OldQuestionDetailSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
        }
    )
    def post(self, request):
        serializer = OldQuestionCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        question = OldQuestion.objects.create(
            **serializer.validated_data,
            uploaded_by=request.user,
            status='pending'
        )
        
        return Response(
            OldQuestionDetailSerializer(question).data,
            status=status.HTTP_201_CREATED
        )

class OldQuestionListView(APIView):
    """
    GET /api/v1/notes/old-questions/
    
     List all published question papers
     Everyone can view (no authentication required)
     Supports filtering and search
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="List Old Questions",
        operation_id="old_question_list",
        description="""
        List all published old question papers.
        
        **Filters:**
        - subject: Filter by subject ID
        - class_level: Filter by class level ID
        - exam_year: Filter by exam year
        - search: Search by title
        
        **Note:** Only 'published' questions are visible to the public.
        """,
        parameters=[
            OpenApiParameter(
                name='subject', 
                description='Filter by subject ID', 
                required=False, 
                type=int
            ),
            OpenApiParameter(
                name='class_level', 
                description='Filter by class level ID', 
                required=False, 
                type=int
            ),
            OpenApiParameter(
                name='exam_year', 
                description='Filter by exam year (e.g., 2080)', 
                required=False, 
                type=int
            ),
            OpenApiParameter(
                name='search', 
                description='Search by title (case-insensitive)', 
                required=False, 
                type=str
            ),
        ],
        responses={200: OldQuestionListSerializer(many=True)}
    )
    def get(self, request):
        queryset = OldQuestion.objects.filter(status='published')
        
        filters = {}
        if subject := request.query_params.get('subject'):
            filters['subject_id'] = subject
        if class_level := request.query_params.get('class_level'):
            filters['class_level_id'] = class_level
        if exam_year := request.query_params.get('exam_year'):
            filters['exam_year'] = exam_year
        
        queryset = queryset.filter(**filters)
        
        if search := request.query_params.get('search'):
            queryset = queryset.filter(title__icontains=search)
        
        queryset = queryset.order_by('-exam_year', '-created_at')
        
        serializer = OldQuestionListSerializer(queryset, many=True)
        return Response(serializer.data)

class OldQuestionDetailView(APIView):
    """
    GET /api/v1/notes/old-questions/{id}/
    
    View full question paper
     Everyone can view published questions
     Teachers can view their own questions (any status)
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Get Old Question Details",
        operation_id="old_question_detail",
        description="""
        View full question paper content.
        
        **Access Rules:**
        - Published questions: Anyone can view
        - Pending/Rejected questions: Only the uploading teacher can view
        - Non-existent or restricted: Returns 404
        """,
        responses={
            200: OldQuestionDetailSerializer,
            404: OpenApiResponse(description="Question not found or not available"),
        }
    )
    def get(self, request, pk):
        question = get_object_or_404(OldQuestion, pk=pk)
        
        # Permission check
        is_owner = question.uploaded_by == request.user if request.user.is_authenticated else False
        is_public = question.status == 'published'
        
        if not is_public and not is_owner:
            return Response(
                {'error': 'Question not available'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Track views for published questions
        if question.status == 'published':
            question.views += 1
            question.save(update_fields=['views'])
        
        serializer = OldQuestionDetailSerializer(question)
        return Response(serializer.data)

class OldQuestionUpdateView(APIView):
    """
    PATCH /api/v1/notes/old-questions/{id}/update/
    
     Update own question
     Only the teacher who created it can update
     Only 'pending' questions can be updated
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Update Old Question",
        operation_id="old_question_update",
        description="""
        Update a question paper.
        
        **Rules:**
        1. Only the teacher who created it can update
        2. Only 'pending' questions can be updated
        3. Partial updates allowed (send only fields to change)
        
        **Cannot update:**
        - Published questions (already approved)
        - Rejected questions (must resubmit)
        """,
        request=OldQuestionUpdateSerializer,
        responses={
            200: OldQuestionDetailSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Question not found"),
        }
    )
    def patch(self, request, pk):
        question = get_object_or_404(OldQuestion, pk=pk)
        
        if not self._can_update(request, question):
            return Response(
                {'error': 'Only the teacher who created this can update it'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check status
        if question.status != 'pending':
            return Response(
                {'error': f'Questions in {question.status} status cannot be updated'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = OldQuestionUpdateSerializer(
            question,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(OldQuestionDetailSerializer(question).data)
    
    def _can_update(self, request, question):
        """Check if user can update the question"""
        if request.user.role == 'admin':
            return True
        return (
            request.user.is_instructor and 
            request.user.is_verified_teacher and 
            question.uploaded_by == request.user
        )

class OldQuestionDeleteView(APIView):
    """
    DELETE /api/v1/notes/old-questions/{id}/delete/
    
     Delete own question
     Only the teacher who created it can delete
     Only 'pending' questions can be deleted
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Delete Old Question",
        operation_id="old_question_delete",
        description="""
        Delete a question paper.
        
        **Rules:**
        1. Only the teacher who created it can delete
        2. Only 'pending' questions can be deleted
        
        **Cannot delete:**
        - Published questions (already approved)
        - Rejected questions (must resubmit if needed)
        """,
        responses={
            204: OpenApiResponse(description="Deleted successfully"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Question not found"),
        }
    )
    def delete(self, request, pk):
        question = get_object_or_404(OldQuestion, pk=pk)
        
        # Check permissions
        if not self._can_delete(request, question):
            return Response(
                {'error': 'Only the teacher who created this can delete it'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check status
        if question.status != 'pending':
            return Response(
                {'error': f'Questions in {question.status} status cannot be deleted'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        question.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    def _can_delete(self, request, question):
        """Check if user can delete the question"""
        if request.user.role == 'admin':
            return True
        return (
            request.user.is_instructor and 
            request.user.is_verified_teacher and 
            question.uploaded_by == request.user
        )

class OldQuestionApprovalView(APIView):
    """
    POST /api/v1/notes/old-questions/{id}/approve/
    
     Approve or reject a pending question
     Admin only
    """
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Approve or Reject Old Question",
        operation_id="old_question_approve",
        description="""
        Admin can approve or reject pending questions.
        
        **Approve:**
        - Status changes to 'published'
        - Becomes visible to everyone
        
        **Reject:**
        - Status changes to 'rejected'
        - Requires rejection reason
        - Teacher can view the reason and resubmit
        """,
        request=OldQuestionApprovalSerializer,
        responses={
            200: OpenApiResponse(description="Status updated successfully"),
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied (Admin only)"),
            404: OpenApiResponse(description="Question not found"),
        }
    )
    def post(self, request, pk):
        question = get_object_or_404(OldQuestion, pk=pk)
        
        if question.status != 'pending':
            return Response(
                {'error': f'Question is already {question.status}. Only pending questions can be reviewed.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = OldQuestionApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        if serializer.validated_data['status'] == 'approved':
            question.status = 'published'
            question.rejection_reason = ''
            message = 'Question approved and published successfully.'
        else:
            question.status = 'rejected'
            question.rejection_reason = serializer.validated_data.get('rejection_reason', '')
            message = 'Question rejected.'
        
        question.save()
        
        return Response({
            'status': question.status,
            'message': message,
            'question': OldQuestionDetailSerializer(question).data
        })

class OldQuestionResubmitView(APIView):
    """
    POST /api/v1/notes/old-questions/{id}/resubmit/
    
     Resubmit a rejected question
     Only the teacher who created it or Admin
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Resubmit Rejected Question",
        operation_id="old_question_resubmit",
        description="""
        Resubmit a rejected question for review.
        
        **Rules:**
        1. Only the teacher who created it or Admin can resubmit
        2. Only 'rejected' questions can be resubmitted
        3. Status changes to 'pending' for re-review
        
        **Use Case:**
        - Teacher fixes issues mentioned in rejection reason
        - Resubmits for admin re-review
        """,
        request=OldQuestionResubmitSerializer,
        responses={
            200: OldQuestionDetailSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Question not found"),
        }
    )
    def post(self, request, pk):
        question = get_object_or_404(OldQuestion, pk=pk)
        
        # Check permissions
        if question.uploaded_by != request.user and request.user.role != 'admin':
            return Response(
                {'error': 'Only the teacher who created this or Admin can resubmit it.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if question.status != 'rejected':
            return Response(
                {'error': f'Only rejected questions can be resubmitted. Current status: {question.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        question.status = 'pending'
        question.rejection_reason = ''
        question.save()
        
        return Response({
            'message': 'Question resubmitted successfully for review.',
            'question': OldQuestionDetailSerializer(question).data
        })

class MyOldQuestionsView(APIView):
    """
    GET /api/v1/notes/old-questions/my-questions/
    
     Get all questions uploaded by the current teacher
     Teachers only
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="My Old Questions",
        operation_id="old_question_my",
        description="""
        Get all old questions uploaded by the current teacher.
        
        **Access:** Teachers only
        
        **Includes:** All statuses (pending, published, rejected)
        **Order:** Latest first (by exam year and creation date)
        """,
        responses={
            200: OldQuestionListSerializer(many=True),
            403: OpenApiResponse(description="Permission denied (Teachers only)"),
        }
    )
    def get(self, request):
        if not request.user.is_instructor:
            return Response(
                {'error': 'Only teachers can access their own questions.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        questions = OldQuestion.objects.filter(
            uploaded_by=request.user
        ).order_by('-exam_year', '-created_at')
        
        serializer = OldQuestionListSerializer(questions, many=True)
        return Response(serializer.data)

class OldQuestionRejectInfoView(APIView):
    """
    GET /api/v1/notes/old-questions/{id}/reject-info/
    
     Get rejection details for a rejected question
     Owner or Admin/Editor can view
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Rejection Information",
        operation_id="old_question_reject_info",
        description="""
        Get detailed rejection information for a rejected question.
        
        **Access:**
        - Teacher who created it: Can view their own rejection info
        - Admin/Editor: Can view any rejection info
        - Others: Not allowed
        
        **Includes:**
        - Rejection reason
        - Who rejected
        - When rejected
        - Can resubmit? (boolean)
        """,
        responses={
            200: OpenApiResponse(description="Rejection information"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Question not found"),
        }
    )
    def get(self, request, pk):
        question = get_object_or_404(OldQuestion, pk=pk)
        
        if question.uploaded_by != request.user and request.user.role not in ['admin', 'editor']:
            return Response(
                {'error': 'You do not have permission to view this information.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if question.status != 'rejected':
            return Response({
                'message': 'This question has not been rejected.',
                'status': question.status
            })
        
        return Response({
            'id': question.id,
            'title': question.title,
            'status': question.status,
            'rejection_reason': question.rejection_reason,
            'can_resubmit': True,  
            'question': OldQuestionDetailSerializer(question).data
        })


class OldQuestionStatsView(APIView):
    """
    GET /api/v1/notes/old-questions/stats/
    
     Get statistics about old questions
     Everyone can view (optional)
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Get Old Question Statistics",
        operation_id="old_question_stats",
        description="Get statistics like total questions, by year, by subject, etc.",
        responses={200: OpenApiResponse(description="Statistics data")}
    )
    def get(self, request):
        from django.db.models import Count
        
        total = OldQuestion.objects.filter(status='published').count()
        by_year = OldQuestion.objects.filter(status='published').values('exam_year').annotate(count=Count('id')).order_by('-exam_year')
        
        return Response({
            'total_published': total,
            'by_year': by_year,
            'available_years': OldQuestion.objects.filter(status='published').values_list('exam_year', flat=True).distinct().order_by('-exam_year')
        })