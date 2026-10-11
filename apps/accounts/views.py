import logging
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import RetrieveAPIView, ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.views import TokenObtainPairView
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from django.conf import settings
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.db import transaction
import datetime

from .authentication import SignupTokenAuthentication
from .permissions import HasSignupToken

import jwt
from .tokens import create_signup_token


from .serializers import (
    SignupSerializer,
    StudentProfileCompleteSerializer,
    TeacherProfileCompleteSerializer,
    CustomTokenObtainPairSerializer,
    LogoutSerializer,
    LoginSerializer,
    AdminUserSerializer,
    UserSerializer,
    OTPSendSerializer,
    OTPVerifySerializer,
    StudentProfileUpdateSerializer,
    TeacherProfileUpdateSerializer,
    StudentProfileSerializer,
    AdminUserUpdateSerializer,
    TeacherProfileSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    AdminVerifyTeacherSerializer,TokenRefreshSerializer
)
from .permissions import IsAdmin, IsActiveUser, IsPhoneVerified, HasCompletedProfile
from .models import StudentProfile, TeacherProfile, OTPVerification
from .services import otp_service
from apps.academics.models import School

logger = logging.getLogger(__name__)
User = get_user_model()


# ============================================================================
# SIGNUP & OTP VIEWS
# ============================================================================

class SignupView(APIView):
    """
    Step 1: Capture phone + role, send OTP.
    - No User row is created here.
    - No session tokens are issued here.
    - The User is created only after OTP verification.
    """
    permission_classes = [AllowAny]
    serializer_class = SignupSerializer

    @extend_schema(request=SignupSerializer)
    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data['phone_number']
        role = serializer.validated_data['role']

        # ── Check for existing user ──
        existing = User.objects.filter(phone_number=phone_number).first()

        if existing and existing.profile_completed:
            return Response(
                {'error': 'Account already exists. Please log in.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Decide purpose: RESUME if half-registered, SIGNUP otherwise ──
        if existing and existing.phone_verified and not existing.profile_completed:
            purpose = OTPVerification.Purpose.RESUME
            action = 'resume_signup'
        else:
            purpose = OTPVerification.Purpose.SIGNUP
            action = 'signup'

        # ── Cooldown to prevent OTP spam ──
        recent = OTPVerification.objects.filter(
            phone_number=phone_number,
            created_at__gte=timezone.now() - timedelta(seconds=60),
        ).exists()
        if recent:
            return Response(
                {'error': 'Please wait before requesting another OTP.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # ── Create OTP row (with role). NOT a User. ──
        try:
            otp = otp_service.generate_otp(
                phone_number=phone_number,
                purpose=purpose,
                pending_role=role,
            )
        except Exception as e:
            logger.error(f"OTP send failed for {phone_number[:4]}***: {e}")
            return Response(
                {'error': 'Could not send OTP. Please try again.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            'message': 'OTP sent successfully.',
            'step': 1,
            'next': 'verify_otp',
            'action': action,
            'phone_number': phone_number,
            'expires_in': otp_service.expiry_minutes * 60,
        }, status=status.HTTP_201_CREATED)


class OTPSendView(APIView):
    """Send OTP to a phone number"""
    permission_classes = [AllowAny]
    serializer_class = OTPSendSerializer

    @extend_schema(request=OTPSendSerializer)
    def post(self, request):
        serializer = OTPSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data['phone_number']
        user = User.objects.filter(phone_number=phone_number).first()

        if not user:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        
        # Allow OTP if phone verified BUT profile NOT completed
        if user.phone_verified and user.profile_completed:
            return Response({
                'error': 'Phone already verified and profile completed. Please login.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # If phone verified but profile not complete, still send OTP
        # (This allows users who verified phone but never completed profile)
        if user.phone_verified and not user.profile_completed:
            # Allow OTP for profile completion
            purpose = OTPVerification.Purpose.RESUME
            action = 'resume_signup'
        else:
            # phone_verified=False → first-time signup
            purpose = OTPVerification.Purpose.SIGNUP
            action = 'signup'

        # ── Cooldown check (prevent spam) ──
        recent = OTPVerification.objects.filter(
            phone_number=phone_number,
            created_at__gte=timezone.now() - timedelta(seconds=60),
        ).exists()
        if recent:
            return Response(
                {'error': 'Please wait before requesting another OTP.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        otp = otp_service.generate_otp(phone_number, OTPVerification.Purpose.SIGNUP)

        return Response({
            'message': 'OTP sent successfully.',
            'phone_number': phone_number,
            'expires_in': otp_service.expiry_minutes * 60,
            'phone_verified': user.phone_verified,
            'profile_completed': user.profile_completed
        }, status=status.HTTP_200_OK)


class OTPVerifyView(APIView):
    """
    UNIFIED OTP Verification — handles SIGNUP, RESUME, and PASSWORD_RESET.
    """
    permission_classes = [AllowAny]
    serializer_class = OTPVerifySerializer

    @extend_schema(request=OTPVerifySerializer)
    def post(self, request):
        serializer = OTPVerifySerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)

        otp_code = serializer.validated_data['otp']
        purpose = serializer.validated_data.get(
            'purpose', OTPVerification.Purpose.SIGNUP
        )
        phone_number = serializer.validated_data.get('phone_number')

        if not phone_number:
            return Response(
                {'error': 'phone_number is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Verify OTP FIRST ──
        # Do NOT look up the user before this. For SIGNUP, no User exists yet.
        try:
            otp = otp_service.verify_otp(phone_number, purpose, otp_code)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # ─────────────────────────────────────────────
        # SIGNUP — create the User now (first time)
        # ─────────────────────────────────────────────
        if purpose == OTPVerification.Purpose.SIGNUP:
            user, created = User.objects.get_or_create(
                phone_number=phone_number,
                defaults={
                    'role': otp.pending_role or 'student',
                    'phone_verified': True,
                    'profile_completed': False,
                    'signup_step': 2,
                    'full_name': '',
                    'password': None,
                },
            )

            # If the row already existed (edge case), just update flags
            if not created:
                user.phone_verified = True
                user.signup_step = 2
                user.save(update_fields=['phone_verified', 'signup_step'])

            signup_token = create_signup_token(user)
            return Response({
                'message': 'Phone verified successfully.',
                'step': 2,
                'next': 'complete_profile',
                'action': 'signup',
                'phone_verified': True,
                'profile_completed': False,
                'signup_token': signup_token,
                'user': UserSerializer(user).data,
            }, status=status.HTTP_200_OK)

        # ─────────────────────────────────────────────
        # RESUME — user already exists, just re-issue token
        # ─────────────────────────────────────────────
        if purpose == OTPVerification.Purpose.RESUME:
            user = User.objects.filter(phone_number=phone_number).first()
            if not user:
                # Can't resume a user that doesn't exist
                return Response(
                    {'error': 'No signup in progress for this number.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if user.profile_completed:
                return Response(
                    {'error': 'Profile already completed. Please log in.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            signup_token = create_signup_token(user)
            return Response({
                'message': 'Welcome back. Please finish setting up your account.',
                'step': 2,
                'next': 'complete_profile',
                'action': 'resume_signup',
                'phone_verified': True,
                'profile_completed': False,
                'signup_token': signup_token,
                'user': UserSerializer(user).data,
            }, status=status.HTTP_200_OK)

        # ─────────────────────────────────────────────
        # PASSWORD_RESET — user must already exist
        # ─────────────────────────────────────────────
        if purpose == OTPVerification.Purpose.PASSWORD_RESET:
            user = User.objects.filter(phone_number=phone_number, is_active=True).first()
            if not user:
                return Response(
                    {'error': 'User not found.'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            reset_token = jwt.encode(
                {
                    'phone': phone_number,
                    'purpose': 'reset',
                    'exp': timezone.now() + timedelta(minutes=5),
                },
                settings.SECRET_KEY,
                algorithm='HS256',
            )
            return Response({
                'message': 'OTP verified. You can now reset your password.',
                'verified': True,
                'reset_token': reset_token,
                'phone_number': phone_number,
            }, status=status.HTTP_200_OK)

        # Fallback (shouldn't be reachable with valid purposes)
        return Response({
            'message': 'OTP verified successfully.',
            'verified': True,
        }, status=status.HTTP_200_OK)


# ============================================================================
# PROFILE COMPLETE VIEWS
# ============================================================================

# apps/accounts/views.py

class StudentProfileCompleteView(APIView):
    """
    Step 2: Complete Student Profile 
    """
    authentication_classes = [SignupTokenAuthentication]
    permission_classes = [IsAuthenticated, IsActiveUser, IsPhoneVerified]
    serializer_class = StudentProfileCompleteSerializer

    @extend_schema(
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'full_name': {'type': 'string'},
                    'school': {'type': 'integer', 'description': 'School ID'},
                    'school_name': {'type': 'string', 'description': 'School name (use this if adding new school)'},
                    'school_type': {'type': 'string', 'enum': ['school', 'college', 'university']},
                    'class_level': {'type': 'integer', 'description': 'Class Level ID'},
                    'faculty': {'type': 'integer', 'description': 'Faculty ID'},
                    'address': {'type': 'string'},
                    'email': {'type': 'string', 'format': 'email'},
                    'profile_image': {'type': 'string', 'format': 'binary'},
                    'password': {'type': 'string', 'format': 'password'},
                    'password_confirm': {'type': 'string', 'format': 'password'},
                },
                'required': ['address', 'email', 'password', 'password_confirm']
            }
        },
        responses={200: UserSerializer}
    )
    @transaction.atomic
    def post(self, request):
        user = request.user

        if not user.is_student:
            return Response({
                'error': 'This endpoint is for students only.'
            }, status=status.HTTP_403_FORBIDDEN)

        if not user.phone_verified:
            return Response({
                'error': 'Please verify your phone first.'
            }, status=status.HTTP_400_BAD_REQUEST)

        if user.profile_completed:
            return Response({
                'error': 'Profile already completed.'
            }, status=status.HTTP_400_BAD_REQUEST)

        serializer = StudentProfileCompleteSerializer(
            data=request.data,
            context={'user': user}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        school = data.get('school')
        school_name = data.get('school_name')
        school_address = data.get('address', '').strip()  

        
        if school_name and school_name.strip():
            
            existing_school = School.objects.filter(
                name__iexact=school_name.strip(),
                address__iexact=school_address
            ).first()
            
            if existing_school:
                
                school = existing_school
                logger.info(f"Student {user.phone_number[:4]} used existing school: {school_name}")
            else:
                
                same_name_school = School.objects.filter(
                    name__iexact=school_name.strip()
                ).first()
                
                if same_name_school:
                    logger.info(f"School '{school_name}' exists but at different address: {same_name_school.address} (student entered: {school_address})")
                
                
                school = School.objects.create(
                    name=school_name.strip(),
                    address=school_address,
                    school_type=data.get('school_type', 'school'),
                    is_verified=False,  
                    created_by=user
                )
                logger.info(f"Student {user.phone_number[:4]} created new school: {school_name} (unverified)")
        
       
        elif school:
            try:
                school = School.objects.get(id=school.id)
            except School.DoesNotExist:
                return Response({
                    'error': 'Selected school does not exist.'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        
        else:
            return Response({
                'error': 'Either school ID or school name is required.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # ✅ Create StudentProfile - use school's address
        StudentProfile.objects.create(
            user=user,
            school=school,
            school_type=data.get('school_type', 'school'),
            class_level=data.get('class_level'),
            faculty=data.get('faculty'),
            address=school.address,  
            email=data['email'],
            profile_image=data.get('profile_image')
        )

        user.set_password(data['password'])
        user.profile_completed = True
        user.signup_step = 3
        user.email = data['email']
        user.save(update_fields=['profile_completed', 'signup_step', 'email', 'password'])

        refresh = RefreshToken.for_user(user)

        return Response({
            'message': 'Student profile completed successfully!',
            'profile_completed': True,
            'school': {
                'id': school.id,
                'name': school.name,
                'address': school.address,
                'is_verified': school.is_verified,
                'needs_verification': not school.is_verified
            },
            'user': UserSerializer(user).data,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }, status=status.HTTP_200_OK)

# Teacher profile complete view
class TeacherProfileCompleteView(APIView):
    """
    Step 2: Complete Teacher Profile 
    """
    authentication_classes = [SignupTokenAuthentication]
    permission_classes = [IsAuthenticated, IsActiveUser, IsPhoneVerified]
    serializer_class = TeacherProfileCompleteSerializer

    @extend_schema(
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'full_name': {'type': 'string'},
                    'faculty': {'type': 'integer', 'description': 'Faculty ID '},
                    'subjects': {'type': 'array', 'items': {'type': 'integer'}, 'description': 'List of subject IDs'},
                    'schools': {'type': 'array', 'items': {'type': 'integer'}, 'description': 'List of school IDs'},
                    'email': {'type': 'string', 'format': 'email'},
                    'bio': {'type': 'string', 'description': 'Short biography'},
                    'profile_image': {'type': 'string', 'format': 'binary'},
                    'verification_document': {'type': 'string', 'format': 'binary'},
                    'password': {'type': 'string', 'format': 'password'},
                    'password_confirm': {'type': 'string', 'format': 'password'},
                },
                'required': ['faculty', 'subjects', 'schools', 'email', 'verification_document', 'password', 'password_confirm']
            }
        },
        responses={200: UserSerializer}
    )
    @transaction.atomic
    def post(self, request):
        user = request.user

        if not user.is_instructor:
            return Response({
                'error': 'This endpoint is for instructors only.'
            }, status=status.HTTP_403_FORBIDDEN)

        if not user.phone_verified:
            return Response({
                'error': 'Please verify your phone first.'
            }, status=status.HTTP_400_BAD_REQUEST)

        if user.profile_completed:
            return Response({
                'error': 'Profile already completed.'
            }, status=status.HTTP_400_BAD_REQUEST)

        data = {}
        
        for key, value in request.data.items():
            if key not in ['profile_image', 'verification_document']:
                data[key] = value
        
        for key, value in request.FILES.items():
            data[key] = value
        
        if 'subjects' in data and isinstance(data['subjects'], str):
            subjects_str = data['subjects']
            subjects_str = subjects_str.strip('[]')
            if subjects_str:
                data['subjects'] = [int(x.strip()) for x in subjects_str.split(',') if x.strip()]
            else:
                data['subjects'] = []
        
        if 'schools' in data and isinstance(data['schools'], str):
            schools_str = data['schools']
            schools_str = schools_str.strip('[]')
            if schools_str:
                data['schools'] = [int(x.strip()) for x in schools_str.split(',') if x.strip()]
            else:
                data['schools'] = []
        
        if 'faculty' in data and isinstance(data['faculty'], str):
            try:
                data['faculty'] = int(data['faculty'])
            except ValueError:
                pass

        serializer = TeacherProfileCompleteSerializer(
            data=data, 
            context={'user': user}
        )
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        # Create TeacherProfile
        teacher_profile = TeacherProfile.objects.create(
            user=user,
            faculty=validated_data['faculty'],
            email=validated_data['email'],
            bio=validated_data.get('bio', ''),
            profile_image=validated_data.get('profile_image'),
            verification_document=validated_data.get('verification_document'),
        )

        if validated_data.get('subjects'):
            teacher_profile.subjects.set(validated_data['subjects'])

        if validated_data.get('schools'):
            from apps.academics.models import TeacherSchool
            from django.utils import timezone
            
            for school in validated_data['schools']:
                TeacherSchool.objects.create(
                    teacher=teacher_profile,
                    school=school,
                    joined_at=timezone.now()
                )

        # Set password and complete profile
        user.set_password(validated_data['password'])
        user.profile_completed = True
        user.signup_step = 3
        user.email = validated_data['email']
        user.save(update_fields=['profile_completed', 'signup_step', 'email', 'password'])

        refresh = RefreshToken.for_user(user)

        return Response({
            'message': 'Teacher profile completed successfully!',
            'profile_completed': True,
            'status': teacher_profile.status,
            'user': UserSerializer(user).data,
            'profile': TeacherProfileSerializer(teacher_profile).data,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }, status=status.HTTP_200_OK)


# ============================================================================
# PROFILE UPDATE VIEWS
# ============================================================================

class StudentProfileUpdateView(APIView):
    """
    PATCH /profile/student/update/
    Update Student Profile 
    """
    permission_classes = [IsAuthenticated, IsActiveUser, HasCompletedProfile]
    serializer_class = StudentProfileUpdateSerializer

    @extend_schema(
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'school': {'type': 'integer', 'description': 'School ID '},
                    'class_level': {'type': 'integer', 'description': 'Class Level ID'},
                    'faculty': {'type': 'integer', 'description': 'Faculty ID'},
                    'address': {'type': 'string'},
                    'profile_image': {'type': 'string', 'format': 'binary'},
                    'alternative_email': {'type': 'string', 'format': 'email'},
                    'alternative_phone': {'type': 'string'},
                },
            }
        },
        responses={200: StudentProfileSerializer}
    )
    def patch(self, request):
        user = request.user

        if not user.is_student:
            return Response({
                'error': 'This endpoint is for students only.'
            }, status=status.HTTP_403_FORBIDDEN)

        if not hasattr(user, 'student_profile'):
            return Response({
                'error': 'Student profile not found.'
            }, status=status.HTTP_404_NOT_FOUND)

        profile = user.student_profile

        serializer = StudentProfileUpdateSerializer(
            data=request.data,
            context={'user': user, 'profile': profile},
            partial=True
        )
        serializer.is_valid(raise_exception=True)

        serializer.update(profile, serializer.validated_data)

        return Response({
            'message': 'Student profile updated successfully.',
            'profile': StudentProfileSerializer(profile).data,
            'alternative_emails': profile.alternative_emails,
            'alternative_phones': profile.alternative_phones
        }, status=status.HTTP_200_OK)


class TeacherProfileUpdateView(APIView):
    """
    PATCH /profile/teacher/update/
    Update Teacher Profile 
    """
    permission_classes = [IsAuthenticated, IsActiveUser, HasCompletedProfile]
    serializer_class = TeacherProfileUpdateSerializer

    @extend_schema(
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'faculty': {'type': 'integer', 'description': 'Faculty ID '},
                    'subjects': {'type': 'array', 'items': {'type': 'integer'}, 'description': 'List of subject IDs '},
                    'schools': {'type': 'array', 'items': {'type': 'integer'}, 'description': 'List of school IDs '},
                    'bio': {'type': 'string'},
                    'profile_image': {'type': 'string', 'format': 'binary'},
                    'verification_document': {'type': 'string', 'format': 'binary'},
                    'alternative_email': {'type': 'string', 'format': 'email'},
                    'alternative_phone': {'type': 'string'},
                },
            }
        },
        responses={200: TeacherProfileSerializer}
    )
    def patch(self, request):
        user = request.user

        if not user.is_instructor:
            return Response({
                'error': 'This endpoint is for instructors only.'
            }, status=status.HTTP_403_FORBIDDEN)

        if not hasattr(user, 'teacher_profile'):
            return Response({
                'error': 'Teacher profile not found.'
            }, status=status.HTTP_404_NOT_FOUND)

        profile = user.teacher_profile

        serializer = TeacherProfileUpdateSerializer(
            data=request.data,
            context={'user': user, 'profile': profile},
            partial=True
        )
        serializer.is_valid(raise_exception=True)

        serializer.update(profile, serializer.validated_data)

        return Response({
            'message': 'Teacher profile updated successfully.',
            'profile': TeacherProfileSerializer(profile).data,
            'alternative_emails': profile.alternative_emails,
            'alternative_phones': profile.alternative_phones
        }, status=status.HTTP_200_OK)


# ============================================================================
# AUTHENTICATION VIEWS
# ============================================================================

class LoginView(TokenObtainPairView):
    """Login with phone number and password"""
    serializer_class = CustomTokenObtainPairSerializer


class LogoutView(APIView):
    """
    POST /api/v1/auth/logout/ - Logout and blacklist refresh token
    """
    permission_classes = [IsAuthenticated]
    serializer_class = LogoutSerializer

    @extend_schema(request=LogoutSerializer)
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            refresh_token = serializer.validated_data['refresh']
            token = RefreshToken(refresh_token)

            token.blacklist()

            return Response({
                'message': 'Logged out successfully. Please discard your tokens.',
                'success': True
            }, status=status.HTTP_200_OK)

        except TokenError as e:
            logger.error(f"Logout error: {str(e)}")
            return Response({
                'error': 'Invalid refresh token.'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return Response({
                'error': 'Logout failed. Please try again.'
            }, status=status.HTTP_400_BAD_REQUEST)


class MeView(RetrieveAPIView):
    """Get current authenticated user's profile with related data"""
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        user = self.request.user

        if user.is_student and hasattr(user, 'student_profile'):
            StudentProfile.objects.select_related(
                'school', 'class_level', 'faculty'
            ).get(user=user)

        elif user.is_instructor and hasattr(user, 'teacher_profile'):
            TeacherProfile.objects.select_related(
                'faculty'
            ).prefetch_related(
                'subjects', 
                'teacher_schools__school' 
            ).get(user=user)

        return user


class TokenRefreshView(APIView):
    """Refresh JWT access token"""
    permission_classes = [AllowAny]
    serializer_class = TokenRefreshSerializer

    @extend_schema(
        request=TokenRefreshSerializer,
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'access': {'type': 'string'},
                    'refresh': {'type': 'string'}
                }
            },
            401: {'description': 'Invalid refresh token'}
        }
    )
    def post(self, request):
        serializer = TokenRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        refresh_token = serializer.validated_data['refresh']
        
        try:
            refresh = RefreshToken(refresh_token)
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh)
            }, status=status.HTTP_200_OK)
        except TokenError:
            return Response({'error': 'Invalid refresh token'}, status=status.HTTP_401_UNAUTHORIZED)


# ============================================================================
# PASSWORD RESET VIEWS
# ============================================================================

class PasswordResetRequestView(APIView):
    """
    POST /api/v1/auth/password/reset/
    Request password reset (forgot password) or change password (authenticated)
    """
    permission_classes = [AllowAny]
    serializer_class = PasswordResetRequestSerializer

    @extend_schema(request=PasswordResetRequestSerializer)
    def post(self, request):
        serializer = PasswordResetRequestSerializer(
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        # SCENARIO 1: Authenticated User (Change Password)
        if request.user.is_authenticated:
            user = request.user
            new_password = validated_data["new_password"]

            user.set_password(new_password)
            user.save()

            logger.info(f"User {user.phone_number} changed password successfully")

            return Response({
                "message": "Password changed successfully.",
                "action": "change_password"
            }, status=status.HTTP_200_OK)

        # SCENARIO 2: Unauthenticated User (Forgot Password)
        phone_number = validated_data["phone_number"]

        user = User.objects.filter(
            phone_number=phone_number,
            is_active=True
        ).first()

        if user:
            otp_service.generate_otp(
                phone_number,
                OTPVerification.Purpose.PASSWORD_RESET
            )

            logger.info(f"Password reset OTP sent to {phone_number[:4]}")

            return Response({
                "message": "Password reset OTP sent to your registered phone number.",
                "phone_number": phone_number,
                "action": "forgot_password"
            }, status=status.HTTP_200_OK)

        return Response({
            "message": "If an account exists, OTP has been sent."
        }, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    """
    POST /api/v1/auth/password/reset/confirm/ - Reset password
    
    Option 1 - Using reset_token (Recommended):
        {"reset_token": "jwt_token", "new_password": "...", "new_password_confirm": "..."}
    
    Option 2 - Authenticated user (NO phone needed!):
        Header: Authorization: Bearer <access_token>
        Body: {"new_password": "...", "new_password_confirm": "..."}
    
    Option 3 - Using phone_number (Legacy support):
        {"phone_number": "9765299096", "new_password": "...", "new_password_confirm": "..."}
    """
    permission_classes = [AllowAny]
    serializer_class = PasswordResetConfirmSerializer

    @extend_schema(request=PasswordResetConfirmSerializer)
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        new_password = serializer.validated_data['new_password']
        phone_number = None
        user = None

        # Option 1: Using reset_token
        if 'reset_token' in request.data:
            try:
                import jwt
                payload = jwt.decode(
                    request.data['reset_token'],
                    settings.SECRET_KEY,
                    algorithms=['HS256']
                )
                phone_number = payload.get('phone')
                if not phone_number:
                    return Response({
                        'error': 'Invalid reset token.'
                    }, status=status.HTTP_400_BAD_REQUEST)

                user = User.objects.filter(phone_number=phone_number, is_active=True).first()
                logger.info(f"User found via reset_token: {phone_number[:4]}")

            except jwt.ExpiredSignatureError:
                return Response({
                    'error': 'Reset token has expired. Please request a new OTP.'
                }, status=status.HTTP_400_BAD_REQUEST)
            except jwt.InvalidTokenError:
                return Response({
                    'error': 'Invalid reset token.'
                }, status=status.HTTP_400_BAD_REQUEST)

        # Option 2: Authenticated user
        elif request.user and request.user.is_authenticated:
            user = request.user
            phone_number = user.phone_number
            logger.info(f"User found via authentication token: {phone_number[:4]}")

        # Option 3: Using phone_number (legacy)
        else:
            phone_number = serializer.validated_data.get('phone_number')
            if not phone_number:
                return Response({
                    'error': 'phone_number, reset_token, or authentication required.'
                }, status=status.HTTP_400_BAD_REQUEST)
            user = User.objects.filter(phone_number=phone_number, is_active=True).first()
            logger.info(f"User found via phone_number: {phone_number[:4]}")

        if not user:
            return Response({
                'error': 'User not found.'
            }, status=status.HTTP_404_NOT_FOUND)

        # Reset password
        user.set_password(new_password)
        user.save(update_fields=['password'])

        logger.info(f"Password reset successful for user: {phone_number[:4]}")

        return Response({
            'message': 'Password reset successfully. Please login with your new password.'
        }, status=status.HTTP_200_OK)


# ============================================================================
# ADMIN VIEWS
# ============================================================================

class AdminUserListView(ListAPIView):
    """List all users (Admin only)"""
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]
    queryset = User.objects.all()


class AdminUserCreateView(APIView):
    """Create editor user (Admin only)"""
    permission_classes = [IsAdmin]
    serializer_class = AdminUserSerializer

    @extend_schema(request=AdminUserSerializer)
    def post(self, request):
        serializer = AdminUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response({
            'message': 'Editor created successfully.',
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)


class AdminUserUpdateView(APIView):
    """
    PATCH /api/v1/auth/admin/users/{phone_number}/
    Activate or Deactivate a user by phone number (Admin only)
    Can also update role to student/instructor/editor
    """
    permission_classes = [IsAdmin]
    serializer_class = AdminUserUpdateSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='phone_number',
                location='path',
                description='Phone number of the user (10 digits)',
                required=True,
                type=OpenApiTypes.STR
            )
        ],
        request=AdminUserUpdateSerializer,
        responses={
            200: UserSerializer,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        }
    )
    def patch(self, request, phone_number):
        try:
            user = User.objects.get(phone_number=phone_number)
            logger.info(f"User found by phone:  {phone_number[:4]}")
        except User.DoesNotExist:
            return Response({
                'error': f'User not found with phone number: {phone_number}'
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminUserUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        # Prevent role change of Admin user
        if 'role' in validated_data:
            if user.is_admin:
                return Response({
                    'error': 'Cannot change role of an Admin user.'
                }, status=status.HTTP_400_BAD_REQUEST)

        # Prevent self-deactivation
        if 'is_active' in validated_data and validated_data['is_active'] is False:
            if user == request.user:
                return Response({
                    'error': 'You cannot deactivate your own account.'
                }, status=status.HTTP_400_BAD_REQUEST)

        allowed_fields = ['is_active', 'role']
        updated_fields = []

        for field in allowed_fields:
            if field in validated_data:
                setattr(user, field, validated_data[field])
                updated_fields.append(f"{field}={validated_data[field]}")

        user.save(update_fields=allowed_fields)

        logger.info(f"Admin {request.user.phone_number[-4:]} updated user {user.phone_number[-4:]}")

        return Response({
            'message': 'User updated successfully.',
            'user': UserSerializer(user).data
        }, status=status.HTTP_200_OK)


class AdminVerifyTeacherView(APIView):
    """
    PATCH /api/v1/auth/admin/teachers/{phone_number}/verify/
    Admin can verify or unverify a teacher
    """
    permission_classes = [IsAdmin]
    serializer_class = AdminVerifyTeacherSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='phone_number',
                location='path',
                description='Phone number of the teacher (10 digits)',
                required=True,
                type=OpenApiTypes.STR
            )
        ],
        request=AdminVerifyTeacherSerializer,
        responses={
            200: UserSerializer,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        }
    )
    def patch(self, request, phone_number):
        serializer = AdminVerifyTeacherSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        verified = serializer.validated_data['verified']

        try:
            user = User.objects.get(phone_number=phone_number)
        except User.DoesNotExist:
            return Response({
                'error': f'User not found with phone number: {phone_number}'
            }, status=status.HTTP_404_NOT_FOUND)

        if not user.is_instructor:
            return Response({
                'error': 'This user is not a teacher.'
            }, status=status.HTTP_400_BAD_REQUEST)

        if not hasattr(user, 'teacher_profile'):
            return Response({
                'error': 'Teacher profile not found.'
            }, status=status.HTTP_404_NOT_FOUND)
            
        profile = user.teacher_profile
            
        if verified and profile.status == TeacherProfile.Status.VERIFIED:
            return Response({
                'success': False,
                'error': f'Teacher {phone_number} is already verified.',
                'user': UserSerializer(user).data,
                'current_status': profile.status
            }, status=status.HTTP_409_CONFLICT)
            
        if not verified and profile.status == TeacherProfile.Status.NOT_VERIFIED:
            return Response({
                'success': False,
                'error': f'Teacher {phone_number} is already not verified.',
                'user': UserSerializer(user).data,
                'current_status': profile.status
            }, status=status.HTTP_409_CONFLICT)     

        
        if verified:
            profile.status = TeacherProfile.Status.VERIFIED
            message = f'Teacher {phone_number[:4]} has been verified.'
        else:
            profile.status = TeacherProfile.Status.NOT_VERIFIED
            message = f'Teacher {phone_number[:4]} has been unverified.'

        profile.save(update_fields=['status'])

        logger.info(f"Admin {request.user.phone_number[:4]} {message}")

        return Response({
            'message': message,
            'user': UserSerializer(user).data
        }, status=status.HTTP_200_OK)