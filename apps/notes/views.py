from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.html import strip_tags
from drf_spectacular.utils import extend_schema, OpenApiResponse, inline_serializer,OpenApiParameter,OpenApiTypes
from rest_framework import serializers

from .models import Note, OldQuestion, NoteRating, NoteViewRecord 
from .serializers import *
from .permissions import IsVerifiedTeacherOrAdmin, IsAdminOrEditor
from .throttles import TeacherWeeklyUploadThrottle
from .cache_service import increment_view_count, get_view_count
# ============================================================================
# NOTE VIEWS (TWO-PHASE WORKFLOW)
# ============================================================================

class NoteTeacherUploadView(APIView):
    permission_classes = [IsVerifiedTeacherOrAdmin] 
    serializer_class = NoteTeacherUploadSerializer
    throttle_classes = [TeacherWeeklyUploadThrottle]

    @extend_schema(
        summary="Teacher Upload Note PDF",
        request=NoteTeacherUploadSerializer,
        responses={201: OpenApiResponse(description="PDF uploaded, pending editor review")}
    )
    def post(self, request):
        serializer = NoteTeacherUploadSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "PDF uploaded successfully. Pending editor review."}, status=status.HTTP_201_CREATED)


class NoteEditorReviewView(APIView):
    """
    PATCH /api/v1/notes/editor/<id>/review/
    Allows Editors to review, add content, and publish/reject notes.
    """
    permission_classes = [IsAdminOrEditor]
    serializer_class = NoteEditorReviewSerializer

    @extend_schema(
        summary="Editor Review & Publish Note",
        request=NoteEditorReviewSerializer,
        responses={200: OpenApiResponse(description="Note updated")}
    )
    def patch(self, request, pk):
        note = get_object_or_404(Note, pk=pk)
        
        serializer = NoteEditorReviewSerializer(note, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        if 'editor_feedback' in request.data:
            raw_feedback = request.data.get('editor_feedback', '')
            serializer.validated_data['editor_feedback'] = strip_tags(raw_feedback).strip()
            
        updated_note = serializer.save()
        
        return Response({
            'message': f'Note updated to {updated_note.get_status_display()}.',
            'status': updated_note.status,
            'editor_feedback': updated_note.editor_feedback
        }, status=status.HTTP_200_OK)


class NoteRateView(APIView):
    """
    POST /api/v1/notes/<id>/rate/
    Allows a student to rate a published note (1-5 stars).
    """
    permission_classes = [IsAuthenticated]
    serializer_class = NoteRatingSerializer

    @extend_schema(
        summary="Rate a Note (1-5 Stars)",
        request=NoteRatingSerializer,
        responses={
            201: inline_serializer(
                name='NoteRatingResponse',
                fields={
                    'message': serializers.CharField(),
                    'average_rating': serializers.DecimalField(max_digits=3, decimal_places=2),
                    'total_reviews': serializers.IntegerField(),
                }
            )
        }
    )
    def post(self, request, pk):
        note = get_object_or_404(Note, pk=pk, status=Note.Status.PUBLISHED)
        
        if note.uploaded_by == request.user:
            return Response({'error': 'You cannot rate your own note.'}, status=status.HTTP_403_FORBIDDEN)
            
        serializer = NoteRatingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        rating, created = NoteRating.objects.update_or_create(
            note=note,
            user=request.user,
            defaults={
                'rating': serializer.validated_data['rating']
            }
        )
        
        note.update_rating()
        
        return Response(
            {'message': 'Rating submitted successfully.', 'average_rating': note.average_rating, 'total_reviews': note.total_reviews},
            status=status.HTTP_201_CREATED if created else status.HTTP_201_OK
        )


class NoteTeacherListView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NoteTeacherViewSerializer

    @extend_schema(summary="Teacher View Own Notes", responses={200: NoteTeacherViewSerializer(many=True)})
    def get(self, request):
        if request.user.role not in ['instructor', 'admin']:
            return Response({'error': 'Only teachers can view this.'}, status=status.HTTP_403_FORBIDDEN)
            
        if request.user.role == 'admin':
            notes = Note.objects.all().order_by('-created_at')
        else:
            notes = Note.objects.filter(uploaded_by=request.user).order_by('-created_at')
            
        serializer = NoteTeacherViewSerializer(notes, many=True, context={'request': request})
        return Response(serializer.data)


class NoteStatusListView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NoteTeacherViewSerializer

    @extend_schema(summary="List Notes by Status", responses={200: NoteTeacherViewSerializer(many=True)})
    def get(self, request, note_status):
        valid_statuses = [choice[0] for choice in Note.Status.choices]
        if status not in valid_statuses:
            return Response({'error': 'Invalid status'}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        notes = Note.objects.filter(status=note_status)
        
        if user.role in ['admin', 'editor']:
            notes = Note.objects.filter(status=status).order_by('-created_at')
        elif user.role == 'instructor':
            notes = Note.objects.filter(uploaded_by=user, status=status).order_by('-created_at')
        else:
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = NoteTeacherViewSerializer(notes, many=True, context={'request': request})
        return Response(serializer.data)


class NotePublicListView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotePublicViewSerializer

    @extend_schema(summary="Public List of Published Notes", responses={200: NotePublicViewSerializer(many=True)})
    def get(self, request):
        queryset = Note.objects.filter(status=Note.Status.PUBLISHED)
        
        subject = request.query_params.get('subject')
        chapter = request.query_params.get('chapter')
        search = request.query_params.get('search')
        
        if subject: queryset = queryset.filter(subject_id=subject)
        if chapter: queryset = queryset.filter(chapter_id=chapter)
        if search: queryset = queryset.filter(title__icontains=search)
            
        queryset = queryset.order_by('-published_at')
        serializer = NotePublicViewSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)


class NotePublicDetailView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotePublicViewSerializer

    @extend_schema(summary="Public View Single Note", responses={200: NotePublicViewSerializer})
    def get(self, request, pk):
        note = get_object_or_404(Note, pk=pk)
        
        if note.status != Note.Status.PUBLISHED and request.user.role not in ['admin', 'editor']:
            return Response({'error': 'Note not found or not published.'}, status=status.HTTP_404_NOT_FOUND)
            
        # if note.status == Note.Status.PUBLISHED:
        #     increment_view_count(note.id)
        #     note.views=get_view_count(note.id)
        
        
            
        serializer = NotePublicViewSerializer(note, context={'request': request})
        return Response(serializer.data)


class NoteDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Delete Note", 
        responses={200: OpenApiResponse(description="Note deleted successfully")}
    )
    def delete(self, request, pk):
        note = get_object_or_404(Note, pk=pk)
        user = request.user

        if user.role in ['admin', 'editor']:
            note.delete()
            return Response({'message': 'Note deleted successfully.'}, status=status.HTTP_200_OK)

        if user.role == 'instructor':
            if note.uploaded_by != user:
                return Response({'error': 'You can only delete your own notes.'}, status=status.HTTP_403_FORBIDDEN)
            if note.status == Note.Status.PUBLISHED:
                return Response({'error': 'Published notes cannot be deleted. Please contact an admin.'}, status=status.HTTP_400_BAD_REQUEST)
            note.delete()
            return Response({'message': 'Note deleted successfully.'}, status=status.HTTP_200_OK)

        return Response({'error': 'You do not have permission to delete this note.'}, status=status.HTTP_403_FORBIDDEN)


class NoteTeacherUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NoteTeacherUpdateSerializer
    throttle_classes = [TeacherWeeklyUploadThrottle] 

    @extend_schema(
        summary="Teacher Update Note (Resubmit)",
        request=NoteTeacherUpdateSerializer,
        responses={200: NoteTeacherViewSerializer}
    )
    def patch(self, request, pk):
        note = get_object_or_404(Note, pk=pk)
        
        if note.uploaded_by != request.user:
            return Response({'error': 'You can only update your own notes.'}, status=status.HTTP_403_FORBIDDEN)
            
        if note.status not in [Note.Status.PENDING, Note.Status.REJECTED]:
            return Response(
                {'error': f'Notes in {note.get_status_display()} status cannot be updated. Contact an admin.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = NoteTeacherUpdateSerializer(note, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_note = serializer.save()
        
        return Response({
            'message': 'Note updated and resubmitted for review.',
            'note': NoteTeacherViewSerializer(updated_note, context={'request': request}).data
        }, status=status.HTTP_200_OK)



class NoteRegisterEngagementView(APIView):
    """
    POST /api/v1/notes/<id>/register-view/
    Called by the frontend ONLY after the user stays for 30s and scrolls 50%.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Register a Verified View",
        request=EngagementPayloadSerializer,
        responses={200: OpenApiResponse(description="View registered successfully")}
    )
    def post(self, request, pk):
        note = get_object_or_404(Note, pk=pk, status=Note.Status.PUBLISHED)
        serializer = EngagementPayloadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        
        dwell_time = serializer.validated_data['dwell_time_seconds']
        scroll_depth = serializer.validated_data['scroll_depth_percentage']
        
        if dwell_time < 30:
            return Response(
                {'error': 'Dwell time too short. Must be at least 30 seconds.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        if scroll_depth < 50:
            return Response(
                {'error': 'Scroll depth too low. Must scroll at least 50%.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        #checks if user already viewes the note
        view_record, created = NoteViewRecord.objects.get_or_create(
            note=note,
            user=request.user
            
        )

        if created:
            # First time this user passed the gate for this note
            note.increment_views() # Safely increments the DB and Redis if you use it
            
            # OPTIONAL: Award points to the student for reading
            if hasattr(request.user, 'student_profile'):
                student = request.user.student_profile
                student.points_balance += 10
                student.save(update_fields=['points_balance'])
                
            return Response(
                {'message': 'View registered successfully!', 'views': note.views}, 
                status=status.HTTP_201_CREATED
            )
        else:
            # User already read this note previously
            return Response(
                {'message': 'View already registered.', 'views': note.views}, 
                status=status.HTTP_200_OK
            )
# ============================================================================
# OLD QUESTION VIEWS
# ============================================================================
class OldQuestionCreateView(APIView):
    """POST /api/v1/notes/old-questions/create/"""
    permission_classes = [IsAdminOrEditor]
    serializer_class = OldQuestionCreateSerializer

    @extend_schema(
        summary="Upload Old Question Paper (Admin/Editor only)",
        request=OldQuestionCreateSerializer,
        responses={201: OldQuestionDetailSerializer}
    )
    def post(self, request):
        serializer = OldQuestionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        question = serializer.save(uploaded_by=request.user)
        
        return Response(
            OldQuestionDetailSerializer(question).data, 
            status=status.HTTP_201_CREATED
        )


class OldQuestionListView(APIView):
    """
    GET /api/v1/notes/old-questions/
    Visible to all authenticated users. Filters by subject and class_level.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = OldQuestionListSerializer

    @extend_schema(
        summary="List Old Questions",
        parameters=[
            OpenApiParameter('subject', OpenApiTypes.INT, description='Filter by Subject ID'),
            OpenApiParameter('class_level', OpenApiTypes.INT, description='Filter by Class Level ID'),
            OpenApiParameter('exam_year', OpenApiTypes.INT, description='Filter by Exam Year'),
            OpenApiParameter('search', OpenApiTypes.STR, description='Search by title'),
        ],
        responses={200: OldQuestionListSerializer(many=True)}
    )
    def get(self, request):
        queryset = OldQuestion.objects.filter(is_active=True).select_related(
            'subject', 'class_level', 'uploaded_by'
        )
        subject_id = request.query_params.get('subject')
        class_level_id = request.query_params.get('class_level')
        exam_year = request.query_params.get('exam_year')
        search = request.query_params.get('search')

        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)
        if class_level_id:
            queryset = queryset.filter(class_level_id=class_level_id)
        if exam_year:
            queryset = queryset.filter(exam_year=exam_year)
        if search:
            queryset = queryset.filter(title__icontains=search)

        serializer = OldQuestionListSerializer(queryset, many=True)
        return Response(serializer.data)


class OldQuestionDetailView(APIView):
    """GET /api/v1/notes/old-questions/{id}/"""
    permission_classes = [IsAuthenticated]
    serializer_class = OldQuestionDetailSerializer

    @extend_schema(summary="View Single Old Question")
    def get(self, request, pk):
        # Only allow viewing if active, or if user is admin/editor
        queryset = OldQuestion.objects.select_related('subject', 'class_level', 'uploaded_by')
        
        if request.user.role in ['admin', 'editor']:
            question = get_object_or_404(queryset, pk=pk)
        else:
            question = get_object_or_404(queryset, pk=pk, is_active=True)

        return Response(OldQuestionDetailSerializer(question).data)


class OldQuestionUpdateView(APIView):
    """PATCH /api/v1/notes/old-questions/{id}/update/"""
    permission_classes = [IsAdminOrEditor]
    serializer_class = OldQuestionUpdateSerializer

    @extend_schema(
        summary="Update Old Question (Admin/Editor only)",
        responses={200: OpenApiResponse(description="Old Question updated successfully")}
    )
    def patch(self, request, pk):
        question = get_object_or_404(OldQuestion, pk=pk)
        
        serializer = OldQuestionUpdateSerializer(question, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({
            "message": "Old Question updated successfully.",
            "question": OldQuestionDetailSerializer(question).data
        }, status=status.HTTP_200_OK)


class OldQuestionDeleteView(APIView):
    """DELETE /api/v1/notes/old-questions/{id}/delete/"""
    permission_classes = [IsAdminOrEditor]

    @extend_schema(summary="Deactivate Old Question (Admin/Editor only)")
    def delete(self, request, pk):
        question = get_object_or_404(OldQuestion, pk=pk)
        
        question.is_active = False
        question.save(update_fields=['is_active'])
        
        return Response(
            {'message': 'Old Question deactivated successfully.'}, 
            status=status.HTTP_200_OK
        )