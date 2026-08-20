# apps/academics/urls.py
from django.urls import path
from .views import (
    # Schools
    SchoolListCreateView,
    SchoolDetailView,
    SchoolVerifyView,
    # VerifiedSchoolsView,
    MySchoolsView,
    # Faculties
    FacultyListCreateView,
    FacultyDetailView,
    # Class Levels
    ClassLevelListCreateView,
    ClassLevelDetailView,
    # Subjects
    SubjectListCreateView,
    SubjectDetailView,
    ChapterDetailView,
    ChapterListCreateView,
    # SubjectsByFacultyView,
    # SubjectsByClassLevelView,
    # Teacher Schools
    TeacherSchoolListView,
    MyTeacherSchoolsView,
)

urlpatterns = [
    # ============ SCHOOLS ============
    path('schools/', SchoolListCreateView.as_view(), name='school-list-create'),
    path('schools/<int:pk>/', SchoolDetailView.as_view(), name='school-detail'),
    path('schools/<int:pk>/verify/', SchoolVerifyView.as_view(), name='school-verify'),
    # path('schools/verified/', VerifiedSchoolsView.as_view(), name='schools-verified'),
    path('schools/my_schools/', MySchoolsView.as_view(), name='my-schools'),

    # ============ FACULTIES ============
    path('faculties/', FacultyListCreateView.as_view(), name='faculty-list-create'),
    path('faculties/<int:pk>/', FacultyDetailView.as_view(), name='faculty-detail'),

    # ============ CLASS LEVELS ============
    path('class-levels/', ClassLevelListCreateView.as_view(), name='classlevel-list-create'),
    path('class-levels/<int:pk>/', ClassLevelDetailView.as_view(), name='classlevel-detail'),

    # ============ SUBJECTS ============
    path('subjects/', SubjectListCreateView.as_view(), name='subject-list-create'),
    path('subjects/<int:pk>/', SubjectDetailView.as_view(), name='subject-detail'),
    # path('subjects/by_faculty/', SubjectsByFacultyView.as_view(), name='subjects-by-faculty'),
    # path('subjects/by_class_level/', SubjectsByClassLevelView.as_view(), name='subjects-by-class-level'),
    path('chapters/', ChapterListCreateView.as_view(), name='chapter-list-create'), 
    path('chapters/<int:pk>/', ChapterDetailView.as_view(), name='chapter-detail'),

    # ============ TEACHER SCHOOLS ============
    path('teacher-schools/', TeacherSchoolListView.as_view(), name='teacherschool-list'),
    path('teacher-schools/my_schools/', MyTeacherSchoolsView.as_view(), name='teacherschool-my'),
]