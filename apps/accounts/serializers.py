from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import User, StudentProfile, TeacherProfile
from .validators import validate_nepali_phone_number
from drf_spectacular.utils import extend_schema_field
import re
# ============================================================================
# PROFILE SERIALIZERS (Display)
# ============================================================================
class StudentProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentProfile
        fields = [
            'school_name', 'school_type', 'class_level', 'faculty',
            'district', 'municipality', 'email', 'points_balance',
            'alternative_emails', 'alternative_phones',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['points_balance', 'created_at', 'updated_at']
class TeacherProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeacherProfile
        fields = [
            'faculty', 'subject', 'schools', 'email', 'rating_avg',
            'content_limit', 'content_count', 'bio',
            'alternative_emails', 'alternative_phones',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['rating_avg', 'content_limit', 'content_count', 'created_at', 'updated_at']

# ============================================================================
# SIGNUP SERIALIZER
# ============================================================================
class SignupSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    middle_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150)
    phone_number = serializers.CharField(max_length=10)
    role = serializers.ChoiceField(choices=[('student', 'Student'), ('instructor', 'Instructor')])

    def validate_phone_number(self, value):
        if not re.match(r'^[9][8][4-9]\d{7}$', value):
            raise serializers.ValidationError(
                "Invalid phone number format. Must be a valid Nepali phone number."
            )
        
        if User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("Phone number already exists.")
        return value

    def create(self, validated_data):
        phone_number = validated_data.pop('phone_number')
        return User.objects.create_user(
            phone_number=phone_number,
            password='',
            first_name=validated_data.get('first_name'),
            middle_name=validated_data.get('middle_name', ''),
            last_name=validated_data.get('last_name'),
            email='',
            role=validated_data.get('role'),
            phone_verified=False,
            is_active=True,
            signup_step=1,
            profile_completed=False
        )
# ============================================================================
# PROFILE COMPLETE SERIALIZERS
# ============================================================================
class StudentProfileCompleteSerializer(serializers.Serializer):
    school_name = serializers.CharField(max_length=200)
    school_type = serializers.ChoiceField(choices=[('school', 'School'), ('college', 'College')])
    class_level = serializers.CharField(max_length=50)
    faculty = serializers.CharField(max_length=100, required=False, allow_blank=True)
    district = serializers.CharField(max_length=100)
    municipality = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)

    def validate_email(self, value):
        user = self.context.get('user')
        
        if User.objects.filter(email=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("This email is already in use.")
        
        if StudentProfile.objects.filter(alternative_emails__contains=[value]).exists():
            raise serializers.ValidationError("This email is already used as alternative email.")
        
        if TeacherProfile.objects.filter(alternative_emails__contains=[value]).exists():
            raise serializers.ValidationError("This email is already used as alternative email.")
        
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        
        password = attrs['password']
        errors = []
        
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long.")
        if not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter.")
        if not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter.")
        if not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit.")
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            errors.append("Password must contain at least one special character.")
        
        if errors:
            raise serializers.ValidationError({"password": errors})
        
        try:
            validate_password(attrs['password'])
        except ValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})
        
        return attrs

class TeacherProfileCompleteSerializer(serializers.Serializer):
    faculty = serializers.CharField(max_length=100)
    subject = serializers.CharField(max_length=100)
    schools = serializers.CharField(help_text="Comma separated school names")
    email = serializers.EmailField()
    bio = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)

    def validate_email(self, value):
        user = self.context.get('user')
        
        if User.objects.filter(email=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("This email is already in use.")
        
        if StudentProfile.objects.filter(alternative_emails__contains=[value]).exists():
            raise serializers.ValidationError("This email is already used as alternative email.")
        
        if TeacherProfile.objects.filter(alternative_emails__contains=[value]).exists():
            raise serializers.ValidationError("This email is already used as alternative email.")
        
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        
        password = attrs['password']
        errors = []
        
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long.")
        if not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter.")
        if not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter.")
        if not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit.")
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            errors.append("Password must contain at least one special character.")
        
        if errors:
            raise serializers.ValidationError({"password": errors})
        
        try:
            validate_password(attrs['password'])
        except ValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})
        
        return attrs


# ============================================================================
# PROFILE UPDATE SERIALIZERS
# ============================================================================

class StudentProfileUpdateSerializer(serializers.Serializer):
    school_name = serializers.CharField(max_length=200, required=False)
    district = serializers.CharField(max_length=100, required=False)
    municipality = serializers.CharField(max_length=100, required=False)
    class_level = serializers.CharField(max_length=50, required=False)
    faculty = serializers.CharField(max_length=100, required=False, allow_blank=True)
    alternative_email = serializers.CharField(required=False, allow_blank=True)
    alternative_phone = serializers.CharField(required=False, allow_blank=True)

    def validate_alternative_email(self, value):
        if not value:
            return value
        
        user = self.context.get('user')
        profile = self.context.get('profile')
        
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value):
            raise serializers.ValidationError("Invalid email format.")
        
        if user and user.email == value:
            raise serializers.ValidationError("This is your primary email. Use a different email as alternative.")
        
        if profile and value in profile.alternative_emails:
            raise serializers.ValidationError("This email is already in your alternative emails list.")
        
        if User.objects.filter(email=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("This email is already registered as primary email by another user.")
        
        if profile:
            if StudentProfile.objects.exclude(id=profile.id).filter(alternative_emails__contains=[value]).exists():
                raise serializers.ValidationError("This email is already used as alternative email by another student.")
        else:
            if StudentProfile.objects.filter(alternative_emails__contains=[value]).exists():
                raise serializers.ValidationError("This email is already used as alternative email by another student.")
        
        if TeacherProfile.objects.filter(alternative_emails__contains=[value]).exists():
            raise serializers.ValidationError("This email is already used as alternative email by a teacher.")
        
        return value

    def validate_alternative_phone(self, value):
        if not value:
            return value
        
        user = self.context.get('user')
        profile = self.context.get('profile')
        
        if not re.match(r'^[9][8][4-9]\d{7}$', value):
            raise serializers.ValidationError(
                "Invalid phone number format. Must be a valid Nepali phone number (e.g., 9841234567)."
            )
        
        if user and user.phone_number == value:
            raise serializers.ValidationError("This is your primary phone number. Use a different number as alternative.")
        
        if profile and value in profile.alternative_phones:
            raise serializers.ValidationError("This phone number is already in your alternative phones list.")
        
        if User.objects.filter(phone_number=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("This phone number is already registered as primary by another user.")
        
        if profile:
            if StudentProfile.objects.exclude(id=profile.id).filter(alternative_phones__contains=[value]).exists():
                raise serializers.ValidationError("This phone number is already used as alternative by another student.")
        else:
            if StudentProfile.objects.filter(alternative_phones__contains=[value]).exists():
                raise serializers.ValidationError("This phone number is already used as alternative by another student.")
        
        if TeacherProfile.objects.filter(alternative_phones__contains=[value]).exists():
            raise serializers.ValidationError("This phone number is already used as alternative by a teacher.")
        
        return value

    def update(self, instance, validated_data):
        profile_fields = ['school_name', 'district', 'municipality', 'class_level', 'faculty']
        for field in profile_fields:
            if field in validated_data:
                setattr(instance, field, validated_data[field])
        
        if 'alternative_email' in validated_data and validated_data['alternative_email']:
            email = validated_data['alternative_email']
            if email not in instance.alternative_emails:
                instance.alternative_emails.append(email)
        
        if 'alternative_phone' in validated_data and validated_data['alternative_phone']:
            phone = validated_data['alternative_phone']
            if phone not in instance.alternative_phones:
                instance.alternative_phones.append(phone)
        
        instance.save()
        return instance
class TeacherProfileUpdateSerializer(serializers.Serializer):
    faculty = serializers.CharField(max_length=100, required=False)
    subject = serializers.CharField(max_length=100, required=False)
    schools = serializers.CharField(required=False, help_text="Comma separated school names")
    bio = serializers.CharField(required=False, allow_blank=True)
    alternative_email = serializers.CharField(required=False, allow_blank=True)
    alternative_phone = serializers.CharField(required=False, allow_blank=True)

    def validate_alternative_email(self, value):
        if not value:
            return value
        
        user = self.context.get('user')
        profile = self.context.get('profile')
        
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value):
            raise serializers.ValidationError("Invalid email format.")
        
        if user and user.email == value:
            raise serializers.ValidationError("This is your primary email. Use a different email as alternative.")
        
        if profile and value in profile.alternative_emails:
            raise serializers.ValidationError("This email is already in your alternative emails list.")
        
        if User.objects.filter(email=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("This email is already registered as primary email by another user.")
        
        if StudentProfile.objects.filter(alternative_emails__contains=[value]).exists():
            raise serializers.ValidationError("This email is already used as alternative email by a student.")
        
        if profile:
            if TeacherProfile.objects.exclude(id=profile.id).filter(alternative_emails__contains=[value]).exists():
                raise serializers.ValidationError("This email is already used as alternative email by another teacher.")
        else:
            if TeacherProfile.objects.filter(alternative_emails__contains=[value]).exists():
                raise serializers.ValidationError("This email is already used as alternative email by another teacher.")
        
        return value

    def validate_alternative_phone(self, value):
        if not value:
            return value
        
        user = self.context.get('user')
        profile = self.context.get('profile')
        
        if not re.match(r'^[9][8][4-9]\d{7}$', value):
            raise serializers.ValidationError(
                "Invalid phone number format. Must be a valid Nepali phone number (e.g., 9841234567)."
            )
        
        if user and user.phone_number == value:
            raise serializers.ValidationError("This is your primary phone number. Use a different number as alternative.")
        
        if profile and value in profile.alternative_phones:
            raise serializers.ValidationError("This phone number is already in your alternative phones list.")
        
        if User.objects.filter(phone_number=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("This phone number is already registered as primary by another user.")
        
        if StudentProfile.objects.filter(alternative_phones__contains=[value]).exists():
            raise serializers.ValidationError("This phone number is already used as alternative by a student.")
        
        if profile:
            if TeacherProfile.objects.exclude(id=profile.id).filter(alternative_phones__contains=[value]).exists():
                raise serializers.ValidationError("This phone number is already used as alternative by another teacher.")
        else:
            if TeacherProfile.objects.filter(alternative_phones__contains=[value]).exists():
                raise serializers.ValidationError("This phone number is already used as alternative by another teacher.")
        
        return value

    def update(self, instance, validated_data):
        profile_fields = ['faculty', 'subject', 'schools', 'bio']
        for field in profile_fields:
            if field in validated_data:
                setattr(instance, field, validated_data[field])
        
        if 'alternative_email' in validated_data and validated_data['alternative_email']:
            email = validated_data['alternative_email']
            if email not in instance.alternative_emails:
                instance.alternative_emails.append(email)
        
        if 'alternative_phone' in validated_data and validated_data['alternative_phone']:
            phone = validated_data['alternative_phone']
            if phone not in instance.alternative_phones:
                instance.alternative_phones.append(phone)
        
        instance.save()
        return instance


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

    @extend_schema_field(serializers.CharField())
    def get_full_name(self, obj):
        return obj.get_full_name()
    
    @extend_schema_field(serializers.BooleanField())
    def get_has_profile(self, obj):
        if obj.is_student:
            return hasattr(obj, 'student_profile')
        elif obj.is_instructor:
            return hasattr(obj, 'teacher_profile')
        return False
    
    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_profile(self, obj):
        if obj.is_student and hasattr(obj, 'student_profile'):
            return StudentProfileSerializer(obj.student_profile).data
        elif obj.is_instructor and hasattr(obj, 'teacher_profile'):
            return TeacherProfileSerializer(obj.teacher_profile).data
        return None
    
    @extend_schema_field(serializers.DictField())
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
    
    @extend_schema_field(serializers.BooleanField())
    def get_can_login(self, obj):
        return obj.phone_verified and obj.profile_completed and obj.has_usable_password()
    
    @extend_schema_field(serializers.BooleanField())
    def get_has_password(self, obj):
        return obj.has_usable_password()
# ============================================================================
# OTP & LOGIN SERIALIZERS
# ============================================================================

class OTPSendSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=10)

    def validate_phone_number(self, value):
        if not re.match(r'^[9][8][4-9]\d{7}$', value):
            raise serializers.ValidationError(
                "Invalid phone number format. Must be a valid Nepali phone number."
            )
        
        if not User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("No user found with this phone number.")
        return value

class OTPVerifySerializer(serializers.Serializer):
    """
    Unified OTP Verification - Handles BOTH Signup AND Password Reset
    
     For Signup (Authenticated):
        {"otp": "123456", "purpose": "signup"}
        → phone_number auto-detected from token
    
     For Password Reset (Unauthenticated):
        {"otp": "123456", "purpose": "password_reset", "phone_number": "9841234567"}
        → phone_number REQUIRED
    """
    otp = serializers.CharField(
        max_length=6,
        min_length=6,
        help_text="6-digit OTP code"
    )
    purpose = serializers.ChoiceField(
        choices=[
            ('signup', 'Signup Verification'),
            ('password_reset', 'Password Reset')
        ],
        default='signup',
        required=False,
        help_text="Purpose: 'signup' or 'password_reset'"
    )
    #  phone_number is OPTIONAL in Swagger (but validated in code)
    phone_number = serializers.CharField(
        max_length=10,
        required=False,  # ← OPTIONAL in Swagger
        help_text="Phone number (REQUIRED only for unauthenticated users)"
    )
    
    def validate(self, data):
        request = self.context.get('request')
        
        # ============================================================
        #  Scenario 1: Authenticated User (Signup)
        # ============================================================
        if request and request.user.is_authenticated:
            # Remove phone_number if provided (prevent override)
            data.pop('phone_number', None)
            return data
        
        # ============================================================
        #  Scenario 2: Unauthenticated User (Password Reset)
        # ============================================================
        phone_number = data.get('phone_number')
        if not phone_number:
            raise serializers.ValidationError({
                'phone_number': 'Phone number required for unauthenticated users.'
            })
        
        # Validate phone number format
        if not re.match(r'^[9][8][4-9]\d{7}$', phone_number):
            raise serializers.ValidationError({
                'phone_number': 'Invalid phone number format.'
            })
        
        return data

class LoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=10)
    password = serializers.CharField(write_only=True)

    def validate_phone_number(self, value):
        if not re.match(r'^[9][8][4-9]\d{7}$', value):
            raise serializers.ValidationError(
                "Invalid phone number format. Must be a valid Nepali phone number."
            )
        return value

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        
        if not self.user.phone_verified:
            raise serializers.ValidationError("Phone number not verified.")
        if not self.user.profile_completed:
            raise serializers.ValidationError("Profile not completed.")
        if not self.user.has_usable_password():
            raise serializers.ValidationError("Password not set.")
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
    refresh = serializers.CharField()

class PasswordResetRequestSerializer(serializers.Serializer):
    phone_number = serializers.CharField(
        max_length=10, 
        help_text="Registered phone number",
        validators=[validate_nepali_phone_number]
    )

    def validate_phone_number(self, value):
        if not User.objects.filter(phone_number=value, is_active=True).exists():
            raise serializers.ValidationError("No active account found with this phone number.")
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True, min_length=8)
    reset_token = serializers.CharField(required=False, help_text="JWT reset token from OTP verification")

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password_confirm": "Passwords do not match."})
        
        request = self.context.get('request')
        is_authenticated = request and request.user and request.user.is_authenticated
        
        phone_number = request.data.get('phone_number') if request else None
        
        if not is_authenticated and not phone_number and not attrs.get('reset_token'):
            raise serializers.ValidationError({
                'error': 'Either phone_number, reset_token, or authentication is required.'
            })
        
        password = attrs['new_password']
        errors = []
        
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long.")
        if not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter.")
        if not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter.")
        if not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit.")
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            errors.append("Password must contain at least one special character.")
        
        if errors:
            raise serializers.ValidationError({"new_password": errors})
        
        try:
            validate_password(attrs['new_password'])
        except ValidationError as e:
            raise serializers.ValidationError({"new_password": list(e.messages)})
        
        return attrs

class AdminUserSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    middle_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150)
    phone_number = serializers.CharField(max_length=10)
    email = serializers.EmailField(required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=[('editor', 'Editor')])
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)

    def validate_phone_number(self, value):
        if not re.match(r'^[9][8][4-9]\d{7}$', value):
            raise serializers.ValidationError(
                "Invalid phone number format. Must be a valid Nepali phone number."
            )
        
        if User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("Phone number already exists.")
        return value

    def validate_email(self, value):
        if value and User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists.")
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        
        password = attrs['password']
        errors = []
        
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long.")
        if not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter.")
        if not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter.")
        if not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit.")
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            errors.append("Password must contain at least one special character.")
        
        if errors:
            raise serializers.ValidationError({"password": errors})
        
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
class AdminUserUpdateSerializer(serializers.Serializer):
    """
    Serializer for Admin to activate/deactivate users
    """
    is_active = serializers.BooleanField(
        required=False,
        help_text="Activate (true) or deactivate (false) the user"
    )
    role = serializers.ChoiceField(
        choices=[
            ('student', 'Student'),
            ('instructor', 'Instructor'),
            ('editor', 'Editor')
        ],
        required=False,
        help_text="Change user role (student, instructor, or editor)"
    )

    def validate(self, attrs):
        # At least one field must be provided
        if not attrs:
            raise serializers.ValidationError(
                "At least one field (is_active or role) must be provided."
            )
        return attrs