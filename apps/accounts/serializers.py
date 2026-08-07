from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import User, StudentProfile, TeacherProfile
from .validators import validate_nepali_phone_number
from drf_spectacular.utils import extend_schema_field
import re

#  Import validators
from .validators import validate_nepali_phone_number,validate_image_file,validate_verification_document


# ============================================================================
# PROFILE SERIALIZERS (Display)
# ============================================================================

class StudentProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentProfile
        fields = [
            'school_name', 'school_type', 'class_level', 'faculty',
            'address', 'email', 'profile_image', 'points_balance',
            'alternative_emails', 'alternative_phones',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['points_balance', 'created_at', 'updated_at']


class TeacherProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeacherProfile
        fields = [
            'faculty', 'subjects', 'schools', 'email', 'profile_image', 
            'rating_avg', 'content_limit', 'content_count', 'bio',
            'verification_document', 'status',
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
    phone_number = serializers.CharField(
        max_length=10,
        validators=[validate_nepali_phone_number]  #  Uses validator
    )
    role = serializers.ChoiceField(choices=[('student', 'Student'), ('instructor', 'Instructor')])

    def validate_phone_number(self, value):
        #  Format already validated by validator, only check uniqueness
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
    school_type = serializers.ChoiceField(
        choices=[('school', 'School'), ('college', 'College'), ('university', 'University')]
    )
    class_level = serializers.CharField(max_length=50)
    faculty = serializers.CharField(max_length=100, required=False, allow_blank=True)
    address = serializers.CharField(max_length=200, help_text="e.g., Kalanki, Kathmandu")
    email = serializers.EmailField()
    profile_image = serializers.ImageField(
            required=False,
            allow_null=True,
            validators=[validate_image_file],
            help_text="Upload profile image (PNG, JPG, JPEG only, max 5MB)"
    )    
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

    def validate_address(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Address is required.")
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Address must be at least 3 characters long.")
        return value.strip()

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
    subjects = serializers.CharField(
        help_text="Comma separated subjects (e.g., Physics, Chemistry, Mathematics)",
        required=True
    )
    schools = serializers.CharField(
        help_text="Comma separated school names (e.g., Nightingale School, Global Academy)",
        required=True
    )
    email = serializers.EmailField()
    bio = serializers.CharField(required=False, allow_blank=True)
    profile_image = serializers.ImageField(
        required=False, 
        allow_null=True,
        validators=[validate_image_file],
        help_text="Upload profile image (PNG, JPG, JPEG only, max 5MB)"
    )
    verification_document = serializers.ImageField(
        required=False, 
        allow_null=True,
        validators=[validate_verification_document],
        help_text="Upload verification document (PDF only, max 10MB)"
    )
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)

    def validate_subjects(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("At least one subject is required.")
        
        subject_list = [s.strip() for s in value.split(',') if s.strip()]
        
        if not subject_list:
            raise serializers.ValidationError("Please enter at least one valid subject.")
        
        for subject in subject_list:
            if len(subject) < 2:
                raise serializers.ValidationError(
                    f"'{subject}' is too short. Please enter valid subject names."
                )
            if len(subject) > 100:
                raise serializers.ValidationError(
                    f"'{subject}' is too long. Maximum 100 characters per subject."
                )
        
        return ', '.join(subject_list)

    def validate_schools(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("At least one school is required.")
        
        school_list = [s.strip() for s in value.split(',') if s.strip()]
        
        if not school_list:
            raise serializers.ValidationError("Please enter at least one valid school name.")
        
        for school in school_list:
            if len(school) < 2:
                raise serializers.ValidationError(
                    f"'{school}' is too short. Please enter valid school names."
                )
            if len(school) > 200:
                raise serializers.ValidationError(
                    f"'{school}' is too long. Maximum 200 characters per school."
                )
        
        return ', '.join(school_list)
    
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
    address = serializers.CharField(max_length=200, required=False, help_text="e.g., Kalanki, Kathmandu")
    class_level = serializers.CharField(max_length=50, required=False)
    faculty = serializers.CharField(max_length=100, required=False, allow_blank=True)
    profile_image = serializers.ImageField(
            required=False,
            allow_null=True,
            validators=[validate_image_file],  #  Only PNG, JPG, JPEG
            help_text="Upload profile image (PNG, JPG, JPEG only, max 5MB)"
    )    
    alternative_email = serializers.CharField(required=False, allow_blank=True)
    alternative_phone = serializers.CharField(required=False, allow_blank=True)

    def validate_address(self, value):
        if value and not value.strip():
            raise serializers.ValidationError("Address cannot be empty.")
        return value.strip() if value else value
    
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
        
        #  Use validator for format
        from .validators import validate_nepali_phone_number
        validate_nepali_phone_number(value)
        
        user = self.context.get('user')
        profile = self.context.get('profile')
        
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
        profile_fields = ['school_name', 'address', 'class_level', 'faculty', 'profile_image']
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
    subjects = serializers.CharField(
        required=False,
        help_text="Comma separated subjects (e.g., Physics, Chemistry, Mathematics)"
    )
    schools = serializers.CharField(
        required=False,
        help_text="Comma separated school names (e.g., Nightingale School, Global Academy)"
    )
    bio = serializers.CharField(required=False, allow_blank=True)
    profile_image = serializers.ImageField(
        required=False,
        allow_null=True,
        validators=[validate_image_file],  #  Only PNG, JPG, JPEG
        help_text="Upload profile image (PNG, JPG, JPEG only, max 5MB)"
    )
    
    verification_document = serializers.ImageField(
        required=False,
        allow_null=True,
        validators=[validate_verification_document],
        help_text="Upload verification document (PDF only, max 10MB)"
    )
    alternative_email = serializers.CharField(required=False, allow_blank=True)
    alternative_phone = serializers.CharField(required=False, allow_blank=True)

    def validate_subjects(self, value):
        if not value or not value.strip():
            return value
        
        subject_list = [s.strip() for s in value.split(',') if s.strip()]
        
        if not subject_list:
            return value
        
        for subject in subject_list:
            if len(subject) < 2:
                raise serializers.ValidationError(
                    f"'{subject}' is too short. Please enter valid subject names."
                )
            if len(subject) > 100:
                raise serializers.ValidationError(
                    f"'{subject}' is too long. Maximum 100 characters per subject."
                )
        
        return ', '.join(subject_list)

    def validate_schools(self, value):
        if not value or not value.strip():
            return value
        
        school_list = [s.strip() for s in value.split(',') if s.strip()]
        
        if not school_list:
            return value
        
        for school in school_list:
            if len(school) < 2:
                raise serializers.ValidationError(
                    f"'{school}' is too short. Please enter valid school names."
                )
            if len(school) > 200:
                raise serializers.ValidationError(
                    f"'{school}' is too long. Maximum 200 characters per school."
                )
        
        return ', '.join(school_list)

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
        
        #  Use validator for format
        from .validators import validate_nepali_phone_number
        validate_nepali_phone_number(value)
        
        user = self.context.get('user')
        profile = self.context.get('profile')
        
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
        # Handle subjects - convert comma string to JSON list
        if 'subjects' in validated_data and validated_data['subjects']:
            subject_list = [s.strip() for s in validated_data['subjects'].split(',') if s.strip()]
            instance.subjects = subject_list
            del validated_data['subjects']
        
        # Handle schools - convert comma string to JSON list
        if 'schools' in validated_data and validated_data['schools']:
            school_list = [s.strip() for s in validated_data['schools'].split(',') if s.strip()]
            instance.schools = school_list
            del validated_data['schools']
        
        profile_fields = ['faculty', 'bio', 'profile_image', 'verification_document']
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
    is_verified_teacher = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = (
            'id', 'first_name', 'middle_name', 'last_name', 'full_name',
            'phone_number', 'email', 'username', 'role',
            'phone_verified', 'profile_completed', 'signup_step',
            'is_active', 'is_staff', 'is_superuser',
            'created_at', 'updated_at',
            'profile', 'permissions', 'has_profile', 'can_login', 
            'has_password', 'is_verified_teacher'
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
        permissions = {}
        
        if obj.is_admin:
            permissions = {
                'is_admin': True,
                'can_manage_users': True,
                'can_manage_content': True,
                'can_approve_content': True,
                'can_view_analytics': True,
                'can_manage_payments': True,
            }
        elif obj.is_student:
            permissions = {
                'is_student': True,
                'can_view_content': True,
                'can_participate_quizzes': True,
                'can_ask_questions': True,
            }
        elif obj.is_instructor:
            permissions = {
                'is_instructor': True,
                'can_manage_content': True,
                'is_verified_teacher': obj.is_verified_teacher,
            }
        elif obj.is_editor:
            permissions = {
                'is_editor': True,
                'can_approve_content': True,
            }
        
        return permissions
    
    @extend_schema_field(serializers.BooleanField())
    def get_can_login(self, obj):
        return obj.phone_verified and obj.profile_completed and obj.has_usable_password()
    
    @extend_schema_field(serializers.BooleanField())
    def get_has_password(self, obj):
        return obj.has_usable_password()
    
    @extend_schema_field(serializers.BooleanField())
    def get_is_verified_teacher(self, obj):
        if obj.is_instructor:
            return obj.is_verified_teacher
        return None


# ============================================================================
# OTP & LOGIN SERIALIZERS
# ============================================================================

class OTPSendSerializer(serializers.Serializer):
    phone_number = serializers.CharField(
        max_length=10,
        validators=[validate_nepali_phone_number]  #  Uses validator
    )

    def validate_phone_number(self, value):
        if not User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("No user found with this phone number.")
        return value


class OTPVerifySerializer(serializers.Serializer):
    otp = serializers.CharField(max_length=6, min_length=6)
    purpose = serializers.ChoiceField(
        choices=[
            ('signup', 'Signup Verification'),
            ('password_reset', 'Password Reset')
        ],
        default='signup',
        required=False,
        help_text="Purpose: 'signup' or 'password_reset'"
    )
    phone_number = serializers.CharField(
        max_length=10,
        required=False,
        help_text="Phone number (REQUIRED only for unauthenticated users)"
    )
    
    def validate(self, data):
        request = self.context.get('request')
        
        if request and request.user.is_authenticated:
            data.pop('phone_number', None)
            return data
        
        phone_number = data.get('phone_number')
        if not phone_number:
            raise serializers.ValidationError({
                'phone_number': 'Phone number required for unauthenticated users.'
            })
        
        #  Validate format
        validate_nepali_phone_number(phone_number)
        
        return data


class LoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField(
        max_length=10,
        validators=[validate_nepali_phone_number]  #  Uses validator
    )
    password = serializers.CharField(write_only=True)

    def validate_phone_number(self, value):
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
    """
    Password Reset/Change Serializer - Dynamic based on auth status
    
    For Unauthenticated (Forgot Password):
        Body: {"phone_number": "9841234567"}
        → Only phone_number allowed
    
    For Authenticated (Change Password):
        Header: Authorization: Bearer <access_token>
        Body: {
            "old_password": "CurrentPass@123#",
            "new_password": "NewSecure@456#",
            "confirm_password": "NewSecure@456#"
        }
        → Only password fields allowed
    """
    
    # For Forgot Password (Unauthenticated)
    phone_number = serializers.CharField(
        max_length=10,
        required=False,
        help_text="Registered phone number (Required for forgot password)",
        validators=[validate_nepali_phone_number] 
    )

    # For Change Password (Authenticated)
    old_password = serializers.CharField(
        required=False,
        write_only=True,
        style={"input_type": "password"},
        help_text="Current password (Required for change password)"
    )

    new_password = serializers.CharField(
        required=False,
        write_only=True,
        style={"input_type": "password"},
        help_text="New password (Required for change password)"
    )

    confirm_password = serializers.CharField(
        required=False,
        write_only=True,
        style={"input_type": "password"},
        help_text="Confirm new password (Required for change password)"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        
        if request and request.user and request.user.is_authenticated:
            #  Authenticated: Show ONLY password fields
            self.fields['phone_number'].required = False
            self.fields['phone_number'].help_text = "Not required for authenticated users"
            self.fields['old_password'].required = True
            self.fields['new_password'].required = True
            self.fields['confirm_password'].required = True
        else:
            #  Unauthenticated: Show ONLY phone_number
            self.fields['phone_number'].required = True
            self.fields['old_password'].required = False
            self.fields['old_password'].help_text = "Not required for forgot password"
            self.fields['new_password'].required = False
            self.fields['new_password'].help_text = "Use /password/reset/confirm/ to set password"
            self.fields['confirm_password'].required = False
            self.fields['confirm_password'].help_text = "Use /password/reset/confirm/ to set password"

    def validate(self, attrs):
        request = self.context.get("request")
        user = request.user if request else None

        # ============================================================
        # AUTHENTICATED USER (Change Password)
        # ============================================================
        if user and user.is_authenticated:
            old_password = attrs.get("old_password")
            new_password = attrs.get("new_password")
            confirm_password = attrs.get("confirm_password")

            # Old password is required
            if not old_password:
                raise serializers.ValidationError({
                    "old_password": "Old password is required to change your password."
                })

            # New password is required
            if not new_password:
                raise serializers.ValidationError({
                    "new_password": "New password is required."
                })

            # Confirm password is required
            if not confirm_password:
                raise serializers.ValidationError({
                    "confirm_password": "Please confirm your new password."
                })

            # Passwords must match
            if new_password != confirm_password:
                raise serializers.ValidationError({
                    "confirm_password": "Passwords do not match."
                })

            # Old password must be correct
            if not user.check_password(old_password):
                raise serializers.ValidationError({
                    "old_password": "Old password is incorrect."
                })

            # New password must be different
            if old_password == new_password:
                raise serializers.ValidationError({
                    "new_password": "New password must be different from the old password."
                })

            # Validate password strength
            try:
                validate_password(new_password)
            except ValidationError as e:
                raise serializers.ValidationError({
                    "new_password": list(e.messages)
                })

            # Phone number NOT allowed for authenticated users
            if attrs.get("phone_number"):
                raise serializers.ValidationError({
                    "phone_number": "Phone number is not required for authenticated users."
                })

            return attrs

        # ============================================================
        # UNAUTHENTICATED USER (Forgot Password)
        # ============================================================
        else:
            phone_number = attrs.get("phone_number")

            # Phone number is required
            if not phone_number:
                raise serializers.ValidationError({
                    "phone_number": "Phone number is required to reset your password."
                })

            # Account must exist
            if not User.objects.filter(
                phone_number=phone_number,
                is_active=True
            ).exists():
                raise serializers.ValidationError({
                    "phone_number": "No active account found with this phone number."
                })

            # Old password NOT allowed for unauthenticated users
            if attrs.get("old_password"):
                raise serializers.ValidationError({
                    "old_password": "Old password is not required for password reset."
                })

            # New password NOT allowed here (will be set in confirm step)
            if attrs.get("new_password") or attrs.get("confirm_password"):
                raise serializers.ValidationError({
                    "error": "Please use /password/reset/confirm/ to set your new password after OTP verification."
                })

            return attrs


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
    phone_number = serializers.CharField(
        max_length=10,
        validators=[validate_nepali_phone_number]  #  Uses validator
    )
    email = serializers.EmailField(required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=[('editor', 'Editor')])
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)

    def validate_phone_number(self, value):
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
        if not attrs:
            raise serializers.ValidationError(
                "At least one field (is_active or role) must be provided."
            )
        return attrs


class AdminVerifyTeacherSerializer(serializers.Serializer):
    verified = serializers.BooleanField(
        required=True,
        help_text="true = verified, false = not_verified"
    )
    
    def validate(self, attrs):
        if 'verified' not in attrs:
            raise serializers.ValidationError({
                'verified': 'This field is required.'
            })
        return attrs