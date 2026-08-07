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

    path('profile/student/update/', views.StudentProfileUpdateView.as_view(), name='student-profile-update'),
    path('profile/teacher/update/', views.TeacherProfileUpdateView.as_view(), name='teacher-profile-update'),
    
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('token/refresh/', views.TokenRefreshView.as_view(), name='token-refresh'),
    path('me/', views.MeView.as_view(), name='me'),
    path('password/reset/', views.PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password/reset/confirm/', views.PasswordResetConfirmView.as_view(), name='password-reset-confirm'),    
    # Admin
    path('admin/users/', views.AdminUserListView.as_view(), name='admin-users'),
    path('admin/users/create/', views.AdminUserCreateView.as_view(), name='admin-user-create'),
    path('admin/users/<str:phone_number>/', views.AdminUserUpdateView.as_view(), name='admin-user-update'),
    path('admin/teachers/<str:phone_number>/verify/', 
         views.AdminVerifyTeacherView.as_view(), 
         name='admin-verify-teacher'),

]