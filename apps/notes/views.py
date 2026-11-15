from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.html import strip_tags
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .models import Note, OldQuestion
from .serializers import *
from .permissions import IsVerifiedTeacherOrAdmin, IsAdminOrEditor

# ============================================================================
# NOTE VIEWS (TWO-PHASE WORKFLOW)
# ============================================================================

class NoteTeacherUploadView(APIView):
    permission_classes = [IsVerifiedTeacherOrAdmin] 

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
    permission_classes = [IsAdminOrEditor]

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


class NoteTeacherListView(APIView):
    permission_classes = [IsAuthenticated]

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

    @extend_schema(summary="List Notes by Status", responses={200: NoteTeacherViewSerializer(many=True)})
    def get(self, request, status):
        valid_statuses = [choice[0] for choice in Note.Status.choices]
        if status not in valid_statuses:
            return Response({'error': 'Invalid status'}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        
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

    @extend_schema(summary="Public View Single Note", responses={200: NotePublicViewSerializer})
    def get(self, request, pk):
        note = get_object_or_404(Note, pk=pk)
        
        if note.status != Note.Status.PUBLISHED and request.user.role not in ['admin', 'editor']:
            return Response({'error': 'Note not found or not published.'}, status=status.HTTP_404_NOT_FOUND)
            
        if note.status == Note.Status.PUBLISHED:
            note.increment_views()
            
        serializer = NotePublicViewSerializer(note, context={'request': request})
        return Response(serializer.data)


class NoteDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Delete Note", responses={204: OpenApiResponse(description="Note deleted")})
    def delete(self, request, pk):
        note = get_object_or_404(Note, pk=pk)
        user = request.user

        if user.role in ['admin', 'editor']:
            note.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        if user.role == 'instructor':
            if note.uploaded_by != user:
                return Response({'error': 'You can only delete your own notes.'}, status=status.HTTP_403_FORBIDDEN)
            if note.status == Note.Status.PUBLISHED:
                return Response({'error': 'Published notes cannot be deleted. Please contact an admin.'}, status=status.HTTP_400_BAD_REQUEST)
            note.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        return Response({'error': 'You do not have permission to delete this note.'}, status=status.HTTP_403_FORBIDDEN)


# ============================================================================
# OLD QUESTION VIEWS
# ============================================================================

class OldQuestionCreateView(APIView):
    permission_classes = [IsVerifiedTeacherOrAdmin]

    def post(self, request):
        serializer = OldQuestionCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        question = OldQuestion.objects.create(**serializer.validated_data, uploaded_by=request.user, status='pending')
        return Response(OldQuestionDetailSerializer(question).data, status=status.HTTP_201_CREATED)

class OldQuestionListView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        queryset = OldQuestion.objects.filter(status='published')
        filters = {}
        if subject := request.query_params.get('subject'): filters['subject_id'] = subject
        if class_level := request.query_params.get('class_level'): filters['class_level_id'] = class_level
        if exam_year := request.query_params.get('exam_year'): filters['exam_year'] = exam_year
        queryset = queryset.filter(**filters)
        if search := request.query_params.get('search'): queryset = queryset.filter(title__icontains=search)
        queryset = queryset.order_by('-exam_year', '-created_at')
        return Response(OldQuestionListSerializer(queryset, many=True).data)

class OldQuestionDetailView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, pk):
        question = get_object_or_404(OldQuestion, pk=pk)
        is_owner = question.uploaded_by == request.user if request.user.is_authenticated else False
        if question.status != 'published' and not is_owner and request.user.role not in ['admin', 'editor']:
            return Response({'error': 'Question not available'}, status=status.HTTP_404_NOT_FOUND)
        if question.status == 'published':
            question.views += 1
            question.save(update_fields=['views'])
        return Response(OldQuestionDetailSerializer(question).data)

class OldQuestionUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    def patch(self, request, pk):
        question = get_object_or_404(OldQuestion, pk=pk)
        if not (request.user.role == 'admin' or (request.user.is_instructor and request.user.is_verified_teacher and question.uploaded_by == request.user)):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        if question.status != 'pending':
            return Response({'error': f'Questions in {question.status} status cannot be updated'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = OldQuestionUpdateSerializer(question, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(OldQuestionDetailSerializer(question).data)

class OldQuestionDeleteView(APIView):
    permission_classes = [IsAuthenticated]
    def delete(self, request, pk):
        question = get_object_or_404(OldQuestion, pk=pk)
        if not (request.user.role == 'admin' or (request.user.is_instructor and request.user.is_verified_teacher and question.uploaded_by == request.user)):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        if question.status != 'pending':
            return Response({'error': f'Questions in {question.status} status cannot be deleted'}, status=status.HTTP_400_BAD_REQUEST)
        question.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class OldQuestionApprovalView(APIView):
    permission_classes = [IsAdminUser]
    def post(self, request, pk):
        question = get_object_or_404(OldQuestion, pk=pk)
        if question.status != 'pending':
            return Response({'error': f'Question is already {question.status}.'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = OldQuestionApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data['status'] == 'approved':
            question.status = 'published'
            question.rejection_reason = ''
        else:
            question.status = 'rejected'
            question.rejection_reason = serializer.validated_data.get('rejection_reason', '')
        question.save()
        return Response({'status': question.status, 'message': 'Question updated.', 'question': OldQuestionDetailSerializer(question).data})

class OldQuestionResubmitView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, pk):
        question = get_object_or_404(OldQuestion, pk=pk)
        if question.uploaded_by != request.user and request.user.role != 'admin':
            return Response({'error': 'Only the creator or Admin can resubmit.'}, status=status.HTTP_403_FORBIDDEN)
        if question.status != 'rejected':
            return Response({'error': f'Only rejected questions can be resubmitted.'}, status=status.HTTP_400_BAD_REQUEST)
        question.status = 'pending'
        question.rejection_reason = ''
        question.save()
        return Response({'message': 'Question resubmitted successfully.', 'question': OldQuestionDetailSerializer(question).data})

class MyOldQuestionsView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        if not request.user.is_instructor:
            return Response({'error': 'Only teachers can access this.'}, status=status.HTTP_403_FORBIDDEN)
        questions = OldQuestion.objects.filter(uploaded_by=request.user).order_by('-exam_year', '-created_at')
        return Response(OldQuestionListSerializer(questions, many=True).data)

class OldQuestionRejectInfoView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, pk):
        question = get_object_or_404(OldQuestion, pk=pk)
        if question.uploaded_by != request.user and request.user.role not in ['admin', 'editor']:
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        if question.status != 'rejected':
            return Response({'message': 'Not rejected.', 'status': question.status})
        return Response({'id': question.id, 'title': question.title, 'status': question.status, 'rejection_reason': question.rejection_reason, 'can_resubmit': True, 'question': OldQuestionDetailSerializer(question).data})