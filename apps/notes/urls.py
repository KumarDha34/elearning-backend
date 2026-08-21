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
    path('<int:pk>/approve/', NoteApprovalView.as_view(), name='note-approve'),  # Approve/Reject
    
    # ============================================================
    # INFO
    # ============================================================
    path('<int:pk>/reject-info/', NoteRejectInfoView.as_view(), name='note-reject-info'),  # Rejection info
]