from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import User, StudentProfile, TeacherProfile


# ============================================================================
# PROFILE SERIALIZERS
# ============================================================================

class StudentProfileSerializer(serializers.ModelSerializer):
    """Student Profile Serializer - For display"""
    
    class Meta:
        model = StudentProfile
        fields = [
            'school_name', 'school_type', 'class_level', 'faculty',
            'district', 'municipality', 'email', 'points_balance',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['points_balance', 'created_at', 'updated_at']


class TeacherProfileSerializer(serializers.ModelSerializer):
    """Teacher Profile Serializer - For display"""
    
    class Meta:
        model = TeacherProfile
        fields = [
            'faculty', 'subject', 'schools', 'email', 'rating_avg',
            'content_limit', 'content_count', 'bio',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['rating_avg', 'content_limit', 'content_count', 'created_at', 'updated_at']


# ============================================================================
# SIGNUP SERIALIZER (Phase 1 - NO PASSWORD)
# ============================================================================

class SignupSerializer(serializers.Serializer):
    """
    Phase 1: Signup - NO PASSWORD
    User creates account with basic info only
    Password will be set during profile completion
    """
    first_name = serializers.CharField(max_length=150)
    middle_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150)
    phone_number = serializers.CharField(max_length=10)
    role = serializers.ChoiceField(choices=[('student', 'Student'), ('instructor', 'Instructor')])

    def validate_phone_number(self, value):
        if User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("Phone number already exists.")
        return value

    def create(self, validated_data):
        phone_number = validated_data.pop('phone_number')

        # Create user with NO password (empty string)
        return User.objects.create_user(
            phone_number=phone_number,
            password='',  # No password - will be set in profile phase
            first_name=validated_data.get('first_name'),
            middle_name=validated_data.get('middle_name', ''),
            last_name=validated_data.get('last_name'),
            email='',  # Email will be added in profile phase
            role=validated_data.get('role'),
            phone_verified=False,
            is_active=True,
            signup_step=1,
            profile_completed=False
        )


# ============================================================================
# PROFILE COMPLETION SERIALIZERS (Phase 2 - PASSWORD HERE)
# ============================================================================

class StudentProfileCompleteSerializer(serializers.Serializer):
    """
    Student Profile Completion - PASSWORD HERE
    Email and Password set here
    """
    school_name = serializers.CharField(max_length=200)
    school_type = serializers.ChoiceField(choices=[('school', 'School'), ('college', 'College')])
    class_level = serializers.CharField(max_length=50)
    faculty = serializers.CharField(max_length=100, required=False, allow_blank=True)
    district = serializers.CharField(max_length=100)
    municipality = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)  # Password here
    password_confirm = serializers.CharField(write_only=True, min_length=8)

    def validate_email(self, value):
        user = self.context.get('user')
        if user and User.objects.filter(email=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("This email is already in use.")
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        try:
            validate_password(attrs['password'])
        except ValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})
        return attrs


class TeacherProfileCompleteSerializer(serializers.Serializer):
    """
    Teacher Profile Completion - PASSWORD HERE
    Email and Password set here
    """
    faculty = serializers.CharField(max_length=100)
    subject = serializers.CharField(max_length=100)
    schools = serializers.CharField(help_text="Comma separated school names")
    email = serializers.EmailField()
    bio = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=8)  # Password here
    password_confirm = serializers.CharField(write_only=True, min_length=8)

    def validate_email(self, value):
        user = self.context.get('user')
        if user and User.objects.filter(email=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("This email is already in use.")
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        try:
            validate_password(attrs['password'])
        except ValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})
        return attrs


# ============================================================================
# USER SERIALIZER
# ============================================================================

class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    has_profile = serializers.SerializerMethodField()
    profile = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    can_login = serializers.SerializerMethodField()
    has_password = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = (
            'id', 'first_name', 'middle_name', 'last_name', 'full_name',
            'phone_number', 'email', 'username', 'role',
            'phone_verified', 'profile_completed', 'signup_step',
            'is_active', 'is_staff', 'is_superuser',
            'created_at', 'updated_at',
            'profile', 'permissions', 'has_profile', 'can_login', 'has_password',
        )
        read_only_fields = fields

    def get_full_name(self, obj):
        return obj.get_full_name()
    
    def get_has_profile(self, obj):
        if obj.is_student:
            return hasattr(obj, 'student_profile')
        elif obj.is_instructor:
            return hasattr(obj, 'teacher_profile')
        return False
    
    def get_profile(self, obj):
        if obj.is_student and hasattr(obj, 'student_profile'):
            return StudentProfileSerializer(obj.student_profile).data
        elif obj.is_instructor and hasattr(obj, 'teacher_profile'):
            return TeacherProfileSerializer(obj.teacher_profile).data
        return None
    
    def get_permissions(self, obj):
        return {
            'is_admin': obj.is_admin,
            'is_student': obj.is_student,
            'is_instructor': obj.is_instructor,
            'is_editor': obj.is_editor,
            'can_manage_users': obj.is_admin,
            'can_manage_content': obj.is_instructor or obj.is_admin,
            'can_approve_content': obj.is_editor or obj.is_admin,
            'can_view_analytics': obj.is_admin,
            'can_manage_payments': obj.is_admin,
        }
    
    def get_can_login(self, obj):
        """Check if user can login (phone_verified AND profile_completed AND has_password)"""
        return obj.phone_verified and obj.profile_completed and obj.has_usable_password()
    
    def get_has_password(self, obj):
        """Check if user has set a password"""
        return obj.has_usable_password()


# ============================================================================
# OTP SERIALIZERS
# ============================================================================

class OTPSendSerializer(serializers.Serializer):
    """Send OTP - Requires phone number"""
    phone_number = serializers.CharField(max_length=10)

    def validate_phone_number(self, value):
        if not User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("No user found with this phone number.")
        return value


class OTPVerifySerializer(serializers.Serializer):
    """Verify OTP - Phone number from authenticated user"""
    otp = serializers.CharField(max_length=6)


# ============================================================================
# LOGIN SERIALIZER
# ============================================================================

class LoginSerializer(serializers.Serializer):
    """Login - Phone + Password"""
    phone_number = serializers.CharField(max_length=10)
    password = serializers.CharField(write_only=True)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT with user data in token"""
    
    def validate(self, attrs):
        data = super().validate(attrs)
        
        # Check all conditions for login
        if not self.user.phone_verified:
            raise serializers.ValidationError("Phone number not verified. Please complete signup.")
        if not self.user.profile_completed:
            raise serializers.ValidationError("Profile not completed. Please complete your profile first.")
        if not self.user.has_usable_password():
            raise serializers.ValidationError("Password not set. Please complete your profile.")
        if not self.user.is_active:
            raise serializers.ValidationError("Account is deactivated.")
        
        data['user'] = UserSerializer(self.user).data
        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['full_name'] = user.get_full_name()
        token['phone_verified'] = user.phone_verified
        token['profile_completed'] = user.profile_completed
        token['signup_step'] = user.signup_step
        token['can_login'] = user.phone_verified and user.profile_completed and user.has_usable_password()
        token['has_password'] = user.has_usable_password()
        return token


class LogoutSerializer(serializers.Serializer):
    """Logout - Refresh token"""
    refresh = serializers.CharField()


class PasswordResetSerializer(serializers.Serializer):
    """Password Reset - Combined request and confirm"""
    phone_number = serializers.CharField(max_length=10)
    new_password = serializers.CharField(write_only=True, required=False)
    new_password_confirm = serializers.CharField(write_only=True, required=False)

    def validate_phone_number(self, value):
        if not User.objects.filter(phone_number=value, is_active=True).exists():
            raise serializers.ValidationError("No active account found with this phone number.")
        return value

    def validate(self, attrs):
        if 'new_password' in attrs and 'new_password_confirm' in attrs:
            if attrs['new_password'] != attrs['new_password_confirm']:
                raise serializers.ValidationError({"new_password_confirm": "Passwords do not match."})
            try:
                validate_password(attrs['new_password'])
            except ValidationError as e:
                raise serializers.ValidationError({"new_password": list(e.messages)})
        return attrs


class AdminUserSerializer(serializers.Serializer):
    """Admin - Create Editor users"""
    first_name = serializers.CharField(max_length=150)
    middle_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150)
    phone_number = serializers.CharField(max_length=10)
    email = serializers.EmailField(required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=[('editor', 'Editor')])
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)

    def validate_phone_number(self, value):
        if User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("Phone number already exists.")
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        try:
            validate_password(attrs['password'])
        except ValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        
        return User.objects.create_editor(
            phone_number=validated_data['phone_number'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            middle_name=validated_data.get('middle_name', ''),
            last_name=validated_data['last_name'],
            email=validated_data.get('email', '')
        )