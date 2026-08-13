# apps/academics/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample, OpenApiResponse
from drf_spectacular.types import OpenApiTypes

from .models import School, Faculty, ClassLevel, Subject, TeacherSchool
from .serializers import (
    SchoolSerializer, FacultySerializer, ClassLevelSerializer,
    SubjectSerializer, TeacherSchoolSerializer
)
from apps.accounts.permissions import IsAdmin, IsAdminOrReadOnly


# ============================================================================
# SCHOOLS
# ============================================================================

class SchoolListCreateView(APIView):
    """
    GET /schools/ - List schools with filters
    POST /schools/ - Create a new school (Admin only, auto-verified)
    """
    permission_classes = [IsAdminOrReadOnly]
    serializer_class = SchoolSerializer

    @extend_schema(
        summary="List Schools",
        operation_id="schools_list",
        description="Get a paginated list of schools with optional filters",
        parameters=[
            OpenApiParameter(name='search', description='Search by name', required=False, type=str),
            OpenApiParameter(name='school_type', description='Filter by school type (School, College, University)', required=False, type=str),
            OpenApiParameter(name='is_verified', description='Filter by verification status', required=False, type=bool),
        ],
        responses={
            200: SchoolSerializer(many=True),
            400: OpenApiResponse(description="Invalid filter parameters"),
        }
    )
    def get(self, request):
        queryset = School.objects.all()
        
        search = request.query_params.get('search')
        school_type = request.query_params.get('school_type')
        is_verified = request.query_params.get('is_verified')

        if search:
            queryset = queryset.filter(name__icontains=search)
        if school_type:
            queryset = queryset.filter(school_type=school_type)
        if is_verified is not None:
            queryset = queryset.filter(is_verified=is_verified.lower() == 'true')

        serializer = self.serializer_class(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Create School (Admin only)",
        operation_id="schools_create",
        description="Create a new school. Only admins can create schools. New schools are automatically verified.",
        request=SchoolSerializer,
        responses={
            201: SchoolSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied - Admin only"),
        },
        examples=[
            OpenApiExample(
                'Create School Example',
                value={
                    "name": "Kathmandu Valley School",
                    "address": "Kathmandu, Nepal",
                    "school_type": "School"
                }
            )
        ]
    )
    def post(self, request):
        if not request.user.is_admin:
            return Response(
                {'error': 'Only admins can create schools.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save(
                created_by=request.user,
                is_verified=True
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SchoolDetailView(APIView):
    """
    GET /schools/{id}/ - Get school details
    PATCH /schools/{id}/ - Update school (Admin or Creator only)
    """
    permission_classes = [IsAdminOrReadOnly]
    serializer_class = SchoolSerializer

    def get_object(self, pk):
        return get_object_or_404(School, pk=pk)

    @extend_schema(
        summary="Get School Details",
        operation_id="schools_retrieve",
        description="Get detailed information about a specific school",
        responses={
            200: SchoolSerializer,
            404: OpenApiResponse(description="School not found"),
        }
    )
    def get(self, request, pk):
        school = self.get_object(pk)
        serializer = self.serializer_class(school)
        return Response(serializer.data)

    @extend_schema(
        summary="Partial Update School",
        operation_id="schools_update",
        description="Update specific fields of a school. Only admins or the school creator can update.",
        request=SchoolSerializer,
        responses={
            200: SchoolSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="School not found"),
        },
        examples=[
            OpenApiExample(
                'Update School Example',
                value={
                    "name": "Updated School Name",
                    "address": "New Address",
                    "school_type": "College",
                    "is_verified": False
                }
            )
        ]
    )
    def patch(self, request, pk):
        school = self.get_object(pk)
        
        if not request.user.is_admin and school.created_by != request.user:
            return Response(
                {'error': 'You do not have permission to update this school.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.serializer_class(school, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SchoolVerifyView(APIView):
    """
    POST /schools/{id}/verify/ - Verify a school
    """
    permission_classes = [IsAdmin]

    @extend_schema(
        summary="Verify School (Admin only)",
        operation_id="schools_verify",
        description="Mark a school as verified. Only admins can perform this action.",
        request=None,
        responses={
            200: SchoolSerializer,
            403: OpenApiResponse(description="Permission denied - Admin only"),
            404: OpenApiResponse(description="School not found"),
        }
    )
    def post(self, request, pk):
        school = get_object_or_404(School, pk=pk)
        
        if school.is_verified:
            return Response({
                'success': False,
                'error': 'School is already verified.',
                'school': SchoolSerializer(school).data
            }, status=status.HTTP_400_BAD_REQUEST)  
        
        school.is_verified = True
        school.save(update_fields=['is_verified'])
        
        return Response({
            'message': 'School verified successfully.',
            'school': SchoolSerializer(school).data
        })


# class VerifiedSchoolsView(APIView):
#     """
#     GET /schools/verified/ - Get all verified schools
#     """
#     permission_classes = []
#     serializer_class = SchoolSerializer

#     @extend_schema(
#         summary="Get Verified Schools",
#         operation_id="schools_verified_list",
#         description="Get a list of all verified schools",
#         responses={
#             200: SchoolSerializer(many=True),
#         }
#     )
#     def get(self, request):
#         schools = School.objects.filter(is_verified=True)
#         serializer = self.serializer_class(schools, many=True)
#         return Response(serializer.data)


class MySchoolsView(APIView):
    """
    GET /schools/my_schools/ - Get schools created by current user
    """
    permission_classes = [IsAuthenticated]
    serializer_class = SchoolSerializer

    @extend_schema(
        summary="Get My Created Schools",
        operation_id="schools_my_list",
        description="Get a list of schools created by the current authenticated user",
        responses={
            200: SchoolSerializer(many=True),
            401: OpenApiResponse(description="Authentication required"),
        }
    )
    def get(self, request):
        schools = School.objects.filter(created_by=request.user)
        serializer = self.serializer_class(schools, many=True)
        return Response(serializer.data)


# ============================================================================
# FACULTIES
# ============================================================================

class FacultyListCreateView(APIView):
    """
    GET /faculties/ - List faculties
    POST /faculties/ - Create a new faculty (Admin only)
    """
    permission_classes = [IsAdminOrReadOnly]
    serializer_class = FacultySerializer

    @extend_schema(
        summary="List Faculties",
        operation_id="faculties_list",
        description="Get a list of all faculties",
        parameters=[
            OpenApiParameter(name='search', description='Search by name', required=False, type=str),
        ],
        responses={
            200: FacultySerializer(many=True),
        }
    )
    def get(self, request):
        queryset = Faculty.objects.all()
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
        serializer = self.serializer_class(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Create Faculty (Admin only)",
        operation_id="faculties_create",
        description="Create a new faculty. Only admins can create faculties.",
        request=FacultySerializer,
        responses={
            201: FacultySerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied - Admin only"),
        },
        examples=[
            OpenApiExample(
                'Create Faculty Example',
                value={
                    "name": "Science",
                    "description": "Faculty of Science and Technology"
                }
            )
        ]
    )
    def post(self, request):
        if not request.user.is_admin:
            return Response(
                {'error': 'Only admins can create faculties.'},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class FacultyDetailView(APIView):
    """
    GET /faculties/{id}/ - Get faculty details
    PATCH /faculties/{id}/ - Update faculty (Admin only)
    """
    permission_classes = [IsAdminOrReadOnly]
    serializer_class = FacultySerializer

    def get_object(self, pk):
        return get_object_or_404(Faculty, pk=pk)

    @extend_schema(
        summary="Get Faculty Details",
        operation_id="faculties_retrieve",
        description="Get detailed information about a specific faculty",
        responses={
            200: FacultySerializer,
            404: OpenApiResponse(description="Faculty not found"),
        }
    )
    def get(self, request, pk):
        faculty = self.get_object(pk)
        serializer = self.serializer_class(faculty)
        return Response(serializer.data)

    @extend_schema(
        summary="Partial Update Faculty (Admin only)",
        operation_id="faculties_update",
        description="Update specific fields of a faculty. Only admins can update faculties.",
        request=FacultySerializer,
        responses={
            200: FacultySerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied - Admin only"),
            404: OpenApiResponse(description="Faculty not found"),
        },
        examples=[
            OpenApiExample(
                'Update Faculty Example',
                value={
                    "name": "Updated Faculty Name",
                    "description": "Updated description"
                }
            )
        ]
    )
    def patch(self, request, pk):
        if not request.user.is_admin:
            return Response(
                {'error': 'Only admins can update faculties.'},
                status=status.HTTP_403_FORBIDDEN
            )
        faculty = self.get_object(pk)
        serializer = self.serializer_class(faculty, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# CLASS LEVELS
# ============================================================================

class ClassLevelListCreateView(APIView):
    """
    GET /class-levels/ - List class levels
    POST /class-levels/ - Create a new class level (Admin only)
    """
    permission_classes = [IsAdminOrReadOnly]
    serializer_class = ClassLevelSerializer

    @extend_schema(
        summary="List Class Levels",
        operation_id="class_levels_list",
        description="Get a list of all class levels with optional filters",
        parameters=[
            OpenApiParameter(name='level_type', description='Filter by level type (SEE, +2, bachelor)', required=False, type=str),
            OpenApiParameter(name='search', description='Search by name', required=False, type=str),
        ],
        responses={
            200: ClassLevelSerializer(many=True),
        }
    )
    def get(self, request):
        queryset = ClassLevel.objects.all()
        level_type = request.query_params.get('level_type')
        search = request.query_params.get('search')
        
        if level_type:
            queryset = queryset.filter(level_type=level_type)
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        serializer = self.serializer_class(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Create Class Level (Admin only)",
        operation_id="class_levels_create",
        description="Create a new class level. Only admins can create class levels.",
        request=ClassLevelSerializer,
        responses={
            201: ClassLevelSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied - Admin only"),
        },
        examples=[
            OpenApiExample(
                'Create Class Level Example',
                value={
                    "name": "Grade 12",
                    "level_type": "+2",
                    "display_order": 12
                }
            )
        ]
    )
    def post(self, request):
        if not request.user.is_admin:
            return Response(
                {'error': 'Only admins can create class levels.'},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ClassLevelDetailView(APIView):
    """
    GET /class-levels/{id}/ - Get class level details
    PATCH /class-levels/{id}/ - Update class level (Admin only)
    """
    permission_classes = [IsAdminOrReadOnly]
    serializer_class = ClassLevelSerializer

    def get_object(self, pk):
        return get_object_or_404(ClassLevel, pk=pk)

    @extend_schema(
        summary="Get Class Level Details",
        operation_id="class_levels_retrieve",
        description="Get detailed information about a specific class level",
        responses={
            200: ClassLevelSerializer,
            404: OpenApiResponse(description="Class Level not found"),
        }
    )
    def get(self, request, pk):
        class_level = self.get_object(pk)
        serializer = self.serializer_class(class_level)
        return Response(serializer.data)

    @extend_schema(
        summary="Partial Update Class Level (Admin only)",
        operation_id="class_levels_update",
        description="Update specific fields of a class level. Only admins can update class levels.",
        request=ClassLevelSerializer,
        responses={
            200: ClassLevelSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied - Admin only"),
            404: OpenApiResponse(description="Class Level not found"),
        },
        examples=[
            OpenApiExample(
                'Update Class Level Example',
                value={
                    "name": "Updated Class Name",
                    "display_order": 13
                }
            )
        ]
    )
    def patch(self, request, pk):
        if not request.user.is_admin:
            return Response(
                {'error': 'Only admins can update class levels.'},
                status=status.HTTP_403_FORBIDDEN
            )
        class_level = self.get_object(pk)
        serializer = self.serializer_class(class_level, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# SUBJECTS
# ============================================================================

class SubjectListCreateView(APIView):
    """
    GET /subjects/ - List subjects with filters
    POST /subjects/ - Create a new subject (Admin only)
    """
    permission_classes = [IsAdminOrReadOnly]
    serializer_class = SubjectSerializer

    @extend_schema(
        summary="List Subjects",
        operation_id="subjects_list",
        description="Get a list of all subjects with optional filters",
        parameters=[
            OpenApiParameter(name='faculty', description='Filter by faculty ID', required=False, type=int),
            OpenApiParameter(name='class_level', description='Filter by class level ID', required=False, type=int),
            OpenApiParameter(name='is_active', description='Filter by active status', required=False, type=bool),
            OpenApiParameter(name='search', description='Search by name', required=False, type=str),
        ],
        responses={
            200: SubjectSerializer(many=True),
        }
    )
    def get(self, request):
        queryset = Subject.objects.select_related('faculty', 'class_level')
        
        faculty_id = request.query_params.get('faculty')
        class_level_id = request.query_params.get('class_level')
        is_active = request.query_params.get('is_active')
        search = request.query_params.get('search')

        if faculty_id:
            queryset = queryset.filter(faculty_id=faculty_id)
        if class_level_id:
            queryset = queryset.filter(class_level_id=class_level_id)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        if search:
            queryset = queryset.filter(name__icontains=search)

        serializer = self.serializer_class(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Create Subject (Admin only)",
        operation_id="subjects_create",
        description="Create a new subject. Only admins can create subjects.",
        request=SubjectSerializer,
        responses={
            201: SubjectSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied - Admin only"),
        },
        examples=[
            OpenApiExample(
                'Create Subject Example',
                value={
                    "name": "Mathematics",
                    "faculty": 1,
                    "class_level": 1
                }
            )
        ]
    )
    def post(self, request):
        if not request.user.is_admin:
            return Response(
                {'error': 'Only admins can create subjects.'},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SubjectDetailView(APIView):
    """
    GET /subjects/{id}/ - Get subject details
    PATCH /subjects/{id}/ - Update subject (Admin only)
    """
    permission_classes = [IsAdminOrReadOnly]
    serializer_class = SubjectSerializer

    def get_object(self, pk):
        return get_object_or_404(Subject.objects.select_related('faculty', 'class_level'), pk=pk)

    @extend_schema(
        summary="Get Subject Details",
        operation_id="subjects_retrieve",
        description="Get detailed information about a specific subject",
        responses={
            200: SubjectSerializer,
            404: OpenApiResponse(description="Subject not found"),
        }
    )
    def get(self, request, pk):
        subject = self.get_object(pk)
        serializer = self.serializer_class(subject)
        return Response(serializer.data)

    @extend_schema(
        summary="Partial Update Subject (Admin only)",
        operation_id="subjects_update",
        description="Update specific fields of a subject. Only admins can update subjects.",
        request=SubjectSerializer,
        responses={
            200: SubjectSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied - Admin only"),
            404: OpenApiResponse(description="Subject not found"),
        },
        examples=[
            OpenApiExample(
                'Update Subject Example',
                value={
                    "name": "Updated Mathematics",
                    "is_active": False
                }
            )
        ]
    )
    def patch(self, request, pk):
        if not request.user.is_admin:
            return Response(
                {'error': 'Only admins can update subjects.'},
                status=status.HTTP_403_FORBIDDEN
            )
        subject = self.get_object(pk)
        serializer = self.serializer_class(subject, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# class SubjectsByFacultyView(APIView):
#     """
#     GET /subjects/by_faculty/?faculty_id={id} - Get subjects by faculty
#     """
#     permission_classes = []
#     serializer_class = SubjectSerializer

#     @extend_schema(
#         summary="Get Subjects by Faculty",
#         operation_id="subjects_by_faculty",
#         description="Get all active subjects for a specific faculty",
#         parameters=[
#             OpenApiParameter(name='faculty_id', description='Faculty ID', required=True, type=int),
#         ],
#         responses={
#             200: SubjectSerializer(many=True),
#             400: OpenApiResponse(description="faculty_id parameter is required"),
#         }
#     )
#     def get(self, request):
#         faculty_id = request.query_params.get('faculty_id')
#         if not faculty_id:
#             return Response(
#                 {'error': 'faculty_id parameter is required.'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
#         subjects = Subject.objects.filter(faculty_id=faculty_id, is_active=True)
#         serializer = self.serializer_class(subjects, many=True)
#         return Response(serializer.data)


# class SubjectsByClassLevelView(APIView):
#     """
#     GET /subjects/by_class_level/?class_level_id={id} - Get subjects by class level
#     """
#     permission_classes = []
#     serializer_class = SubjectSerializer

#     @extend_schema(
#         summary="Get Subjects by Class Level",
#         operation_id="subjects_by_class_level",
#         description="Get all active subjects for a specific class level",
#         parameters=[
#             OpenApiParameter(name='class_level_id', description='Class Level ID', required=True, type=int),
#         ],
#         responses={
#             200: SubjectSerializer(many=True),
#             400: OpenApiResponse(description="class_level_id parameter is required"),
#         }
#     )
#     def get(self, request):
#         class_level_id = request.query_params.get('class_level_id')
#         if not class_level_id:
#             return Response(
#                 {'error': 'class_level_id parameter is required.'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
#         subjects = Subject.objects.filter(class_level_id=class_level_id, is_active=True)
#         serializer = self.serializer_class(subjects, many=True)
#         return Response(serializer.data)


# ============================================================================
# TEACHER SCHOOLS
# ============================================================================

class TeacherSchoolListView(APIView):
    """
    GET /teacher-schools/ - List teacher-school affiliations
    """
    permission_classes = [IsAuthenticated]
    serializer_class = TeacherSchoolSerializer

    @extend_schema(
        summary="List Teacher-School Affiliations",
        operation_id="teacher_schools_list",
        description="Get a list of teacher-school affiliations. Teachers see only their own affiliations.",
        parameters=[
            OpenApiParameter(name='teacher', description='Filter by teacher ID (Admin only)', required=False, type=int),
            OpenApiParameter(name='school', description='Filter by school ID', required=False, type=int),
        ],
        responses={
            200: TeacherSchoolSerializer(many=True),
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(description="Permission denied"),
        }
    )
    def get(self, request):
        queryset = TeacherSchool.objects.select_related('teacher__user', 'school')
        
        if not request.user.is_admin:
            try:
                teacher_profile = request.user.teacher_profile
                queryset = queryset.filter(teacher=teacher_profile)
            except:
                queryset = queryset.none()
        
        teacher_id = request.query_params.get('teacher')
        school_id = request.query_params.get('school')
        
        if teacher_id and request.user.is_admin:
            queryset = queryset.filter(teacher_id=teacher_id)
        if school_id:
            queryset = queryset.filter(school_id=school_id)
        
        serializer = self.serializer_class(queryset, many=True)
        return Response(serializer.data)


class MyTeacherSchoolsView(APIView):
    """
    GET /teacher-schools/my_schools/ - Get schools for current teacher
    """
    permission_classes = [IsAuthenticated]
    serializer_class = TeacherSchoolSerializer

    @extend_schema(
        summary="Get My Schools",
        operation_id="teacher_schools_my",
        description="Get all school affiliations for the current authenticated teacher",
        responses={
            200: TeacherSchoolSerializer(many=True),
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(description="Permission denied - Teacher only"),
            404: OpenApiResponse(description="Teacher profile not found"),
        }
    )
    def get(self, request):
        if not request.user.is_instructor:
            return Response(
                {'error': 'Only teachers can access this endpoint.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            teacher = request.user.teacher_profile
            affiliations = TeacherSchool.objects.filter(teacher=teacher)
            serializer = self.serializer_class(affiliations, many=True)
            return Response(serializer.data)
        except:
            return Response(
                {'error': 'Teacher profile not found.'},
                status=status.HTTP_404_NOT_FOUND
            )