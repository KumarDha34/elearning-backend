from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    Phase1SignupView,
    OTPRequestView,
    OTPVerifyView,
    Phase2CompleteProfileView,
    LoginView,
    LogoutView,
    UserProfileView,
    PasswordResetRequestView,
    PasswordResetVerifyView,
    PasswordResetConfirmView,
)

urlpatterns = [
    #Signup part 1 and otp
    path('signup/phase1/', Phase1SignupView.as_view(), name='signup-phase1'),    
    
    path('otp/request/', OTPRequestView.as_view(), name='otp-request'),
    path('otp/verify/', OTPVerifyView.as_view(), name='otp-verify'),
    
    
    #Signup part 2
    path('signup/phase2/', Phase2CompleteProfileView.as_view(), name='signup-phase2'),
    
    #Login & Logout
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    
    #Profile
    path('profile/', UserProfileView.as_view(), name='user-profile'),
    
    # Password Reset
    path('password/reset/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password/reset/verify/', PasswordResetVerifyView.as_view(), name='password-reset-verify'),
    path('password/reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
]