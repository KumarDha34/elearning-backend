from django.urls import path
from . import views

app_name = 'notes'

urlpatterns = [
    # ========================================================================
    # NOTE WORKFLOW (TWO-PHASE)
    # ========================================================================
    
    # 1. Phase 1: Teacher Uploads PDF
    path('teacher/upload/', views.NoteTeacherUploadView.as_view(), name='note-teacher-upload'),
    
    # 2. Teacher Dashboard: View own notes & statuses (pending, rejected, etc.)
    path('teacher/my-notes/', views.NoteTeacherListView.as_view(), name='note-teacher-list'),
    
    # 3. Phase 2: Editor Reviews, adds CKEditor content, and sets status
    path('editor/<int:pk>/review/', views.NoteEditorReviewView.as_view(), name='note-editor-review'),
    
    # 4. Status Filter: Easily get all pending, rejected, or teacher_review notes
    path('status/<str:status>/', views.NoteStatusListView.as_view(), name='note-status-list'),
    
    # 5. Public Display: Only shows PUBLISHED notes
    path('', views.NotePublicListView.as_view(), name='note-public-list'),
    path('<int:pk>/', views.NotePublicDetailView.as_view(), name='note-public-detail'),
    
    # 6. Delete Note (Teachers can delete their own unpublished, Editors/Admins can delete any)
    path('<int:pk>/delete/', views.NoteDeleteView.as_view(), name='note-delete'),
    
    path('teacher/<int:pk>/update/', views.NoteTeacherUpdateView.as_view(), name='note-teacher-update'),

    # ========================================================================
    # OLD QUESTIONS WORKFLOW
    # ========================================================================
    
    # 1. Public Display
    path('old-questions/', views.OldQuestionListView.as_view(), name='old-question-list'),
    path('old-questions/<int:pk>/', views.OldQuestionDetailView.as_view(), name='old-question-detail'),
    
    # 2. Teacher Actions
    path('old-questions/create/', views.OldQuestionCreateView.as_view(), name='old-question-create'),
    path('old-questions/my-questions/', views.MyOldQuestionsView.as_view(), name='old-question-my'),
    path('old-questions/<int:pk>/update/', views.OldQuestionUpdateView.as_view(), name='old-question-update'),
    path('old-questions/<int:pk>/delete/', views.OldQuestionDeleteView.as_view(), name='old-question-delete'),
    path('old-questions/<int:pk>/resubmit/', views.OldQuestionResubmitView.as_view(), name='old-question-resubmit'),
    path('old-questions/<int:pk>/reject-info/', views.OldQuestionRejectInfoView.as_view(), name='old-question-reject-info'),
    
    # 3. Admin Actions
    path('old-questions/<int:pk>/approve/', views.OldQuestionApprovalView.as_view(), name='old-question-approve'),
]