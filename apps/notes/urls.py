from django.urls import path
from .views import (
    NoteListView,
    NoteCreateView,
    NoteDetailView,
    NoteUpdateView,
    NoteDeleteView,
    NoteApprovalView,
    NotePreviewView,
    NoteStatusUpdateView,
    NoteResubmitView,
    NoteRejectInfoView,
    OldQuestionCreateView,
    OldQuestionListView,
    OldQuestionDetailView,
    OldQuestionUpdateView,
    OldQuestionDeleteView,
    OldQuestionApprovalView,
    MyOldQuestionsView,OldQuestionResubmitView
)

urlpatterns = [
    # ============================================================
    # DISPLAY (Everyone)
    # ============================================================
    path('', NoteListView.as_view(), name='note-list'),           # Display notes
    path('<int:pk>/', NoteDetailView.as_view(), name='note-detail'),  # Display note
    
    # ============================================================
    # TEACHER ACTIONS (Verified Teachers Only)
    # ============================================================
    path('create/', NoteCreateView.as_view(), name='note-create'),      # Create note
    path('preview/', NotePreviewView.as_view(), name='note-preview'),    # Preview note
    path('<int:pk>/update/', NoteUpdateView.as_view(), name='note-update'),  # Update note
    path('<int:pk>/delete/', NoteDeleteView.as_view(), name='note-delete'),  # Delete note
    path('<int:pk>/status/', NoteStatusUpdateView.as_view(), name='note-status'),  # Update status
    path('<int:pk>/resubmit/', NoteResubmitView.as_view(), name='note-resubmit'),  # Resubmit rejected
    
    # ============================================================
    # EDITOR/ADMIN ACTIONS
    # ============================================================
    path('<int:pk>/approve/', NoteApprovalView.as_view(), name='note-approve'), 
    
    # ============================================================
    # INFO
    # ============================================================
    path('<int:pk>/reject-info/', NoteRejectInfoView.as_view(), name='note-reject-info'),

    path('old-questions/', OldQuestionListView.as_view(), name='old-question-list'),
    
    # 2. View single question (Everyone - published only)
    path('old-questions/<int:pk>/', OldQuestionDetailView.as_view(), name='old-question-detail'),
    
    # 3. Create/Upload question (Teacher only)
    path('old-questions/create/', OldQuestionCreateView.as_view(), name='old-question-create'),
    
    # 4. Update own question (Teacher - pending only)
    path('old-questions/<int:pk>/update/', OldQuestionUpdateView.as_view(), name='old-question-update'),
    
    path('old-questions/<int:pk>/delete/', OldQuestionDeleteView.as_view(), name='old-question-delete'),
    
    path('old-questions/<int:pk>/approve/', OldQuestionApprovalView.as_view(), name='old-question-approve'),
    
    path('old-questions/my-questions/', MyOldQuestionsView.as_view(), name='old-question-my'),
    path('old-questions/<int:pk>/resubmit/', OldQuestionResubmitView.as_view(), name='old-question-resubmit'),

]