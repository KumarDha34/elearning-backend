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

from .serializers import (
    SignupSerializer, 
    StudentProfileCompleteSerializer,
    TeacherProfileCompleteSerializer,
    CustomTokenObtainPairSerializer,
    LogoutSerializer, 
    LoginSerializer, 
    PasswordResetSerializer, 
    AdminUserSerializer,
    UserSerializer,
    OTPSendSerializer,
    OTPVerifySerializer
)
from .permissions import IsAdmin, IsActiveUser, IsPhoneVerified
from .models import StudentProfile, TeacherProfile, OTPVerification
from .services import otp_service

logger = logging.getLogger(__name__)
User = get_user_model()


class SignupView(APIView):
    """
    PHASE 1: Signup - Password entered here
    Phone number entered ONCE here
    """
    permission_classes = [AllowAny]
    
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
                'otp': otp.otp_code,  # Development only
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
    """
    Send OTP - Resend OTP
    Requires phone_number in request body
    """
    permission_classes = [AllowAny]
    
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
    Verify OTP - Phone number from authenticated user
    No phone_number required in body
    """
    permission_classes = [AllowAny]
    
    @extend_schema(request=OTPVerifySerializer)
    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Get phone number from authenticated user if available
        if request.user and request.user.is_authenticated:
            phone_number = request.user.phone_number
        else:
            # Fallback: get from request body (for unauthenticated)
            phone_number = request.data.get('phone_number')
            if not phone_number:
                return Response(
                    {'error': 'phone_number required for unauthenticated users.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        code = serializer.validated_data['otp']
        
        try:
            otp_service.verify_otp(phone_number, OTPVerification.Purpose.SIGNUP, code)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        user = User.objects.filter(phone_number=phone_number).first()
        if user:
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
        
        return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)


class StudentProfileCompleteView(APIView):
    """
    PHASE 3a: Complete Student Profile -  PASSWORD HERE
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsPhoneVerified]
    
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
        
        # Create Student Profile
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
        
        #  Set password here (user was created with no password)
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
    """
    PHASE 3b: Complete Teacher Profile -  PASSWORD HERE
    """
    permission_classes = [IsAuthenticated, IsActiveUser, IsPhoneVerified]
    
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
        
        # Create Teacher Profile
        TeacherProfile.objects.create(
            user=user,
            faculty=data['faculty'],
            subject=data['subject'],
            schools=data['schools'],
            email=data['email'],
            bio=data.get('bio', '')
        )
        
        #  Set password here (user was created with no password)
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

class LoginView(TokenObtainPairView):
    """
    Login - Phone + Password
    Only allowed if phone_verified AND profile_completed
    """
    serializer_class = CustomTokenObtainPairSerializer


class LogoutView(APIView):
    """Logout - Blacklist refresh token"""
    permission_classes = [IsAuthenticated]
    
    @extend_schema(request=LogoutSerializer)
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            token = RefreshToken(serializer.validated_data['refresh'])
            token.blacklist()
        except TokenError:
            return Response({'error': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({'message': 'Logged out successfully'})


class MeView(RetrieveAPIView):
    """Complete user info - Phase 1 + Phase 2 + Permissions"""
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user


class TokenRefreshView(APIView):
    """Refresh access token"""
    permission_classes = [AllowAny]
    
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


class PasswordResetView(APIView):
    """Password Reset - Combined request and confirm"""
    permission_classes = [AllowAny]
    
    def _request_reset(self, phone_number):
        user = User.objects.filter(phone_number=phone_number, is_active=True).first()
        if user:
            otp = otp_service.generate_otp(phone_number, OTPVerification.Purpose.PASSWORD_RESET)
            return Response({
                'message': 'Password reset OTP sent.',
                'phone_number': phone_number,
                'otp': otp.otp_code
            })
        return Response({'message': 'If an account exists, OTP has been sent.'})
    
    def _confirm_reset(self, phone_number, new_password):
        user = User.objects.filter(phone_number=phone_number, is_active=True).first()
        if user:
            user.set_password(new_password)
            user.save(update_fields=['password'])
            return Response({'message': 'Password reset successfully.'})
        return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request):
        action = request.query_params.get('action', 'request')
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        if action == 'request':
            return self._request_reset(serializer.validated_data['phone_number'])
        else:
            return self._confirm_reset(
                serializer.validated_data['phone_number'],
                serializer.validated_data.get('new_password')
            )


# ============================================================================
# ADMIN VIEWS
# ============================================================================

class AdminUserListView(ListAPIView):
    """List all users - Admin only"""
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]
    queryset = User.objects.all()


class AdminUserCreateView(APIView):
    """Create editor - Admin only"""
    permission_classes = [IsAdmin]
    
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
    """Update user - Admin only"""
    permission_classes = [IsAdmin]
    
    def patch(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        
        allowed_fields = ['is_active', 'role', 'profile_completed']
        for field in allowed_fields:
            if field in request.data:
                setattr(user, field, request.data[field])
        
        user.save(update_fields=allowed_fields)
        
        return Response({
            'message': 'User updated successfully.',
            'user': UserSerializer(user).data
        })


class AdminUserDeleteView(APIView):
    """Delete user - Admin only"""
    permission_classes = [IsAdmin]
    
    def delete(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        
        if user == request.user:
            return Response({'error': 'Cannot delete yourself.'}, status=status.HTTP_400_BAD_REQUEST)
        if user.is_admin:
            return Response({'error': 'Cannot delete another admin.'}, status=status.HTTP_400_BAD_REQUEST)
        
        user.delete()
        return Response({'message': 'User deleted successfully.'})