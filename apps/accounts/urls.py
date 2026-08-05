from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Signup 
    path('signup/', views.SignupView.as_view(), name='signup'),
    
    path('otp/send/', views.OTPSendView.as_view(), name='otp-send'),
    
    path('otp/verify/', views.OTPVerifyView.as_view(), name='otp-verify'),
    
    path('profile/student/complete/', views.StudentProfileCompleteView.as_view(), name='student-profile-complete'),
    
    path('profile/teacher/complete/', views.TeacherProfileCompleteView.as_view(), name='teacher-profile-complete'),
    
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('token/refresh/', views.TokenRefreshView.as_view(), name='token-refresh'),
    path('me/', views.MeView.as_view(), name='me'),
    
    # Password Reset
    path('password/reset/', views.PasswordResetView.as_view(), name='password-reset'),
    
    # Admin
    path('admin/users/', views.AdminUserListView.as_view(), name='admin-users'),
    path('admin/users/create/', views.AdminUserCreateView.as_view(), name='admin-user-create'),
    path('admin/users/<int:user_id>/', views.AdminUserUpdateView.as_view(), name='admin-user-update'),
    path('admin/users/<int:user_id>/delete/', views.AdminUserDeleteView.as_view(), name='admin-user-delete'),
]