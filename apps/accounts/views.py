from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User
from .serializers import (
    Phase1SignupSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    Phase2CompleteProfileSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    UserSerializer
)
from .services import OTPService


class Phase1SignupView(generics.CreateAPIView):
    serializer_class = Phase1SignupSerializer
    permission_classes = [permissions.AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        temp_data = serializer.save()
        
        OTPService.send_otp(temp_data.phone, 'signup')
        return Response({
            'message': 'OTP sent to your phone. Please verify to continue.',
            'phone': temp_data.phone,
            'role': temp_data.role
        }, status=status.HTTP_201_CREATED)


class OTPRequestView(generics.GenericAPIView):
    serializer_class = OTPRequestSerializer
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data['phone']
        purpose = serializer.validated_data.get('purpose', 'signup')
        OTPService.send_otp(phone, purpose)
        return Response({
            'message': f'OTP sent for {purpose}',
            'phone': phone
        })


class OTPVerifyView(generics.GenericAPIView):
    serializer_class = OTPVerifySerializer
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data['phone']
        purpose = serializer.validated_data['purpose']
        
        if purpose == 'signup':
            return Response({
                'message': 'Phone verified successfully',
                'phone': phone,
                'phone_verified': True,
                'next_step': 'Complete your profile with email, address, college, and password.'
            })
            
        elif purpose == 'password_reset':
            return Response({
                'message': 'OTP verified successfully!',
                'phone': phone,
                'phone_verified': True,
                'next_step': 'You can now reset your password.'
            })
        
        return Response({
            'error': 'Invalid purpose'
        }, status=status.HTTP_400_BAD_REQUEST)
        
class Phase2CompleteProfileView(generics.GenericAPIView):
    serializer_class = Phase2CompleteProfileSerializer
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'message': 'Registration complete! You can now login.',
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)


class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data
        })


class LogoutView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            return Response({'message': 'Logged out successfully'})
        except Exception:
            return Response({'message': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)
        
class TokenRefreshView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        from rest_framework_simplejwt.views import TokenRefreshView as JWTTokenRefreshView
        return JWTTokenRefreshView.as_view()(request)


class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user


class PasswordResetRequestView(generics.GenericAPIView):
    serializer_class = OTPRequestSerializer
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data['phone']
        
        if not User.objects.filter(phone=phone).exists():
            return Response({'error': 'No user found'}, status=status.HTTP_404_NOT_FOUND)
        
        OTPService.send_otp(phone, 'password_reset')
        return Response({'message': 'OTP sent for password reset.', 'phone': phone})


class PasswordResetVerifyView(generics.GenericAPIView):
    serializer_class = OTPVerifySerializer
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({'message': 'OTP verified. You can now reset your password.'})


class PasswordResetConfirmView(generics.GenericAPIView):
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'message': 'Password reset successfully!'})