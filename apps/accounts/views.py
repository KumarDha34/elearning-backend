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
from drf_spectacular.utils import extend_schema
from django.conf import settings
import datetime
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes

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
    StudentProfileSerializer, AdminUserUpdateSerializer,
    TeacherProfileSerializer,PasswordResetConfirmSerializer,PasswordResetRequestSerializer
)
from .permissions import IsAdmin, IsActiveUser, IsPhoneVerified, HasCompletedProfile
from .models import StudentProfile, TeacherProfile, OTPVerification
from .services import otp_service

logger = logging.getLogger(__name__)
User = get_user_model()


# ============================================================================
# SIGNUP & OTP VIEWS
# ============================================================================

class SignupView(APIView):
    permission_classes = [AllowAny]
    serializer_class = SignupSerializer
    
    @extend_schema(request=SignupSerializer)
    @transaction.atomic
    def post(self, request):
        try:
            serializer = SignupSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = serializer.save()
            
            otp = otp_service.generate_otp(user.phone_number, OTPVerification.Purpose.SIGNUP)
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'message': 'Step 1 complete. Verify your phone.',
                'step': 1,
                'next': 'otp_verification',
                'phone_number': user.phone_number,
                'otp': otp.otp_code,
                'user': UserSerializer(user).data,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Signup failed: {str(e)}")
            return Response({
                'success': False,
                'error': 'Registration failed. Please try again.',
                'details': str(e) if settings.DEBUG else None
            }, status=status.HTTP_400_BAD_REQUEST)


class OTPSendView(APIView):
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
        
        if user.phone_verified:
            return Response({'error': 'Phone already verified.'}, status=status.HTTP_400_BAD_REQUEST)
        
        otp = otp_service.generate_otp(phone_number, OTPVerification.Purpose.SIGNUP)
        
        return Response({
            'message': 'OTP sent successfully.',
            'phone_number': phone_number,
            'otp': otp.otp_code,
            'expires_in': otp_service.expiry_minutes * 60
        })


class OTPVerifyView(APIView):
    """
    UNIFIED OTP Verification - Handles BOTH Signup AND Password Reset
    """
    permission_classes = [AllowAny]
    serializer_class = OTPVerifySerializer
    
    @extend_schema(request=OTPVerifySerializer)
    def post(self, request):
        # Pass request to serializer context
        serializer = OTPVerifySerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        otp_code = serializer.validated_data['otp']
        purpose = serializer.validated_data.get('purpose', OTPVerification.Purpose.SIGNUP)
        
        if request.user and request.user.is_authenticated:
            phone_number = request.user.phone_number
            user = request.user
            logger.info(f"Phone auto-detected: {phone_number}")
        else:
            phone_number = request.data.get('phone_number')
            if not phone_number:
                return Response({
                    'error': 'phone_number required for unauthenticated users.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            user = User.objects.filter(phone_number=phone_number).first()
            if not user:
                return Response({
                    'error': 'User not found.'
                }, status=status.HTTP_404_NOT_FOUND)
            logger.info(f"Phone provided: {phone_number}")
        
        # ============================================================
        # Verify OTP
        # ============================================================
        try:
            otp_service.verify_otp(phone_number, purpose, otp_code)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        if purpose == OTPVerification.Purpose.SIGNUP:
            user.phone_verified = True
            user.signup_step = 2
            user.save(update_fields=['phone_verified', 'signup_step'])
            
            refresh = RefreshToken.for_user(user)
            return Response({
                'message': 'Phone verified successfully!',
                'step': 2,
                'next': 'complete_profile',
                'phone_verified': True,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UserSerializer(user).data
            })
        
        elif purpose == OTPVerification.Purpose.PASSWORD_RESET:
            import jwt
            reset_token = jwt.encode(
                {
                    'phone': phone_number, 
                    'purpose': 'reset',
                    'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=5)
                },
                settings.SECRET_KEY,
                algorithm='HS256'
            )
            
            return Response({
                'message': 'OTP verified successfully. You can now reset your password.',
                'verified': True,
                'reset_token': reset_token,
                'phone_number': phone_number
            })
        
        return Response({
            'message': 'OTP verified successfully.',
            'verified': True
        })


# ============================================================================
# PROFILE COMPLETE VIEWS
# ============================================================================

class StudentProfileCompleteView(APIView):
    permission_classes = [IsAuthenticated, IsActiveUser, IsPhoneVerified]
    serializer_class = StudentProfileCompleteSerializer
    
    @extend_schema(request=StudentProfileCompleteSerializer)
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
        
        StudentProfile.objects.create(
            user=user,
            school_name=data['school_name'],
            school_type=data.get('school_type', 'school'),
            class_level=data['class_level'],
            faculty=data.get('faculty', ''),
            district=data['district'],
            municipality=data['municipality'],
            email=data['email']
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
            'user': UserSerializer(user).data,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }, status=status.HTTP_200_OK)


class TeacherProfileCompleteView(APIView):
    permission_classes = [IsAuthenticated, IsActiveUser, IsPhoneVerified]
    serializer_class = TeacherProfileCompleteSerializer
    
    @extend_schema(request=TeacherProfileCompleteSerializer)
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
        
        serializer = TeacherProfileCompleteSerializer(
            data=request.data,
            context={'user': user}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        TeacherProfile.objects.create(
            user=user,
            faculty=data['faculty'],
            subject=data['subject'],
            schools=data['schools'],
            email=data['email'],
            bio=data.get('bio', '')
        )
        
        user.set_password(data['password'])
        user.profile_completed = True
        user.signup_step = 3
        user.email = data['email']
        user.save(update_fields=['profile_completed', 'signup_step', 'email', 'password'])
        
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'message': 'Teacher profile completed successfully!',
            'profile_completed': True,
            'user': UserSerializer(user).data,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }, status=status.HTTP_200_OK)


# ============================================================================
#  PROFILE UPDATE VIEWS
# ============================================================================

class StudentProfileUpdateView(APIView):
    """
    PATCH /profile/student/update/
    Update Student Profile - Combined
     Profile Fields: school_name, district, municipality, class_level, faculty
     Alternative Contacts: alternative_email, alternative_phone
     NOT Editable: email (primary), phone_number (primary)
    """
    permission_classes = [IsAuthenticated, IsActiveUser, HasCompletedProfile]
    serializer_class = StudentProfileUpdateSerializer
    
    @extend_schema(request=StudentProfileUpdateSerializer)
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
    Update Teacher Profile - Combined
     Profile Fields: faculty, schools, bio
     Alternative Contacts: alternative_email, alternative_phone
     NOT Editable: email (primary), phone_number (primary), subject
    """
    permission_classes = [IsAuthenticated, IsActiveUser, HasCompletedProfile]
    serializer_class = TeacherProfileUpdateSerializer
    
    @extend_schema(request=TeacherProfileUpdateSerializer)
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
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user


class TokenRefreshView(APIView):
    permission_classes = [AllowAny]
    serializer_class = None

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response({'error': 'Refresh token required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            refresh = RefreshToken(refresh_token)
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh)
            })
        except TokenError:
            return Response({'error': 'Invalid refresh token'}, status=status.HTTP_401_UNAUTHORIZED)


class PasswordResetRequestView(APIView):
    """
    POST /api/v1/auth/password/reset/ - Request password reset OTP
    """
    permission_classes = [AllowAny]
    serializer_class = PasswordResetRequestSerializer
    
    @extend_schema(request=PasswordResetRequestSerializer)
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        phone_number = serializer.validated_data['phone_number']
        user = User.objects.filter(phone_number=phone_number, is_active=True).first()
        
        if user:
            otp = otp_service.generate_otp(phone_number, OTPVerification.Purpose.PASSWORD_RESET)
            return Response({
                'message': 'Password reset OTP sent.',
                'phone_number': phone_number,
                'otp': otp.otp_code 
            })
        
        return Response({
            'message': 'If an account exists, OTP has been sent.'
        })

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
                logger.info(f"User found via reset_token: {phone_number}")
                
            except jwt.ExpiredSignatureError:
                return Response({
                    'error': 'Reset token has expired. Please request a new OTP.'
                }, status=status.HTTP_400_BAD_REQUEST)
            except jwt.InvalidTokenError:
                return Response({
                    'error': 'Invalid reset token.'
                }, status=status.HTTP_400_BAD_REQUEST)
        elif request.user and request.user.is_authenticated:
            user = request.user
            phone_number = user.phone_number
            logger.info(f"User found via authentication token: {phone_number}")
        
        else:
            phone_number = serializer.validated_data.get('phone_number')
            if not phone_number:
                return Response({
                    'error': 'phone_number, reset_token, or authentication required.'
                }, status=status.HTTP_400_BAD_REQUEST)
            user = User.objects.filter(phone_number=phone_number, is_active=True).first()
            logger.info(f"User found via phone_number: {phone_number}")
        
        if not user:
            return Response({
                'error': 'User not found.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Reset password
        user.set_password(new_password)
        user.save(update_fields=['password'])
        
        logger.info(f"Password reset successful for user: {phone_number}")
        
        return Response({
            'message': 'Password reset successfully. Please login with your new password.'
        })

# ============================================================================
# ADMIN VIEWS
# ============================================================================

class AdminUserListView(ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]
    queryset = User.objects.all()


class AdminUserCreateView(APIView):
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
    
    Example: PATCH /admin/users/9841234567/
    
    Request Body:
        {
            "is_active": true/false,
            "role": "student" | "instructor" | "editor"
        }
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
            logger.info(f"User found by phone: {phone_number}")
        except User.DoesNotExist:
            return Response({
                'error': f'User not found with phone number: {phone_number}'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = AdminUserUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        
        if 'role' in validated_data:
            if user.is_admin:
                return Response({
                    'error': 'Cannot change role of an Admin user.'
                }, status=status.HTTP_400_BAD_REQUEST)
        
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
        
        logger.info(f"Admin {request.user.phone_number} updated user {user.phone_number}: {', '.join(updated_fields)}")
        
        return Response({
            'message': 'User updated successfully.',
            'user': UserSerializer(user).data
        }, status=status.HTTP_200_OK)