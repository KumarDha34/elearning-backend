from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import User, StudentProfile, TeacherProfile
from .validators import validate_nepali_phone_number
from drf_spectacular.utils import extend_schema_field
import re
from apps.academics.models import School, Faculty, ClassLevel, Subject, TeacherSchool
# Import validators
from .validators import validate_nepali_phone_number, validate_image_file, validate_verification_document


# ============================================================================
# PROFILE SERIALIZERS (Display)
# ============================================================================

class StudentProfileSerializer(serializers.ModelSerializer):
    """Student Profile Serializer with nested related data"""
    
    school_name = serializers.CharField(source='school.name', read_only=True)
    class_level_name = serializers.CharField(source='class_level.name', read_only=True)
    faculty_name = serializers.CharField(source='faculty.name', read_only=True)
    
    class Meta:
        model = StudentProfile
        fields = [
            'id', 'user',
            'school', 'school_name',
            'school_type',
            'class_level', 'class_level_name',
            'faculty', 'faculty_name',
            'address', 'email', 'profile_image', 'points_balance',
            'alternative_emails', 'alternative_phones',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['points_balance', 'created_at', 'updated_at']


class TeacherProfileSerializer(serializers.ModelSerializer):
    """Teacher Profile Serializer with nested related data"""
    
    faculty_name = serializers.CharField(source='faculty.name', read_only=True)
    subject_names = serializers.SerializerMethodField()
    school_names = serializers.SerializerMethodField()
    
    class Meta:
        model = TeacherProfile
        fields = [
            'id', 'user',
            'faculty', 'faculty_name',
            'subjects', 'subject_names',
            # 'schools', 
            'school_names',
            'email', 'profile_image',
            'rating_avg', 'content_limit', 'content_count', 'bio',
            'verification_document', 'status',
            'alternative_emails', 'alternative_phones',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['rating_avg', 'content_limit', 'content_count', 'created_at', 'updated_at']
    
    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_subject_names(self, obj):
        return list(obj.subjects.values_list('name', flat=True))
    
    # @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    # def get_school_names(self, obj):
    #     return list(obj.schools.values_list('name', flat=True))
    
    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_school_names(self, obj):
        """Get schools with additional details from TeacherSchool model"""
        return [
            {
                'id': ts.school.id,
                'name': ts.school.name,
                'address': ts.school.address,
                'school_type': ts.school.school_type,
                'joined_at': ts.joined_at,
                
            }
            for ts in obj.teacher_schools.all()
        ]


# ============================================================================
# SIGNUP SERIALIZER
# ============================================================================

class SignupSerializer(serializers.Serializer):
    """Step 1: User registration with phone number"""
    
    first_name = serializers.CharField(max_length=150)
    middle_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150)
    phone_number = serializers.CharField(
        max_length=10,
        validators=[validate_nepali_phone_number]
    )
    role = serializers.ChoiceField(choices=[('student', 'Student'), ('instructor', 'Instructor')])

    def validate_phone_number(self, value):
        if User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("Phone number already exists.")
        return value

    def create(self, validated_data):
        phone_number = validated_data.pop('phone_number')
        return User.objects.create_user(
            phone_number=phone_number,
            first_name=validated_data.get('first_name'),
            middle_name=validated_data.get('middle_name', ''),
            last_name=validated_data.get('last_name'),
            role=validated_data.get('role'),
            phone_verified=False,
            is_active=True,
            signup_step=1,
            profile_completed=False
        )


# ============================================================================
# STUDENT PROFILE COMPLETE SERIALIZER
# ============================================================================

class StudentProfileCompleteSerializer(serializers.Serializer):
    """Step 2: Complete Student Profile with Academics ForeignKeys"""
    
    # Academics ForeignKeys (Send IDs from dropdown)
    school = serializers.PrimaryKeyRelatedField(
        queryset=School.objects.filter(is_verified=True),
        required=False,
        allow_null=True,
        help_text="School ID from the schools list"
    )
    
    school_type = serializers.ChoiceField(
        choices=[('school', 'School'), ('college', 'College'), ('university', 'University')],
        default='school'
    )
    
    class_level = serializers.PrimaryKeyRelatedField(
        queryset=ClassLevel.objects.all(),
        required=False,
        allow_null=True,
        help_text="Class Level ID from the classes list"
    )
    
    faculty = serializers.PrimaryKeyRelatedField(
        queryset=Faculty.objects.all(),
        required=False,
        allow_null=True,
        help_text="Faculty ID from the faculties list"
    )
    
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

    def validate_school(self, value):
        if value and not value.is_verified:
            raise serializers.ValidationError("This school is not verified yet.")
        return value

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


# ============================================================================
# TEACHER PROFILE COMPLETE SERIALIZER
# ============================================================================

class TeacherProfileCompleteSerializer(serializers.Serializer):
    """Step 2: Complete Teacher Profile with Academics ForeignKeys"""
    
    # Academics ForeignKeys (Send IDs from dropdown)
    faculty = serializers.PrimaryKeyRelatedField(
        queryset=Faculty.objects.all(),
        required=True,
        help_text="Faculty ID from the faculties list"
    )
    
    subjects = serializers.PrimaryKeyRelatedField(
        queryset=Subject.objects.filter(is_active=True),
        many=True,
        required=True,
        help_text="List of subject IDs"
    )
    
    schools = serializers.PrimaryKeyRelatedField(
        queryset=School.objects.filter(is_verified=True),
        many=True,
        required=True,
        help_text="List of school IDs"
    )
    
    email = serializers.EmailField()
    bio = serializers.CharField(required=False, allow_blank=True)
    profile_image = serializers.ImageField(
        required=False,
        allow_null=True,
        validators=[validate_image_file],
        help_text="Upload profile image (PNG, JPG, JPEG only, max 5MB)"
    )
    verification_document = serializers.FileField(
        required=True,
        allow_null=False,
        validators=[validate_verification_document],
        help_text="Upload verification document (PDF only, max 10MB)"
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
# STUDENT PROFILE UPDATE SERIALIZER
# ============================================================================

class StudentProfileUpdateSerializer(serializers.Serializer):
    """Update Student Profile with ForeignKeys"""
    
    school = serializers.PrimaryKeyRelatedField(
        queryset=School.objects.filter(is_verified=True),
        required=False,
        allow_null=True
    )
    
    class_level = serializers.PrimaryKeyRelatedField(
        queryset=ClassLevel.objects.all(),
        required=False,
        allow_null=True
    )
    
    faculty = serializers.PrimaryKeyRelatedField(
        queryset=Faculty.objects.all(),
        required=False,
        allow_null=True
    )
    
    address = serializers.CharField(max_length=200, required=False, help_text="e.g., Kalanki, Kathmandu")
    profile_image = serializers.ImageField(
        required=False,
        allow_null=True,
        validators=[validate_image_file],
        help_text="Upload profile image (PNG, JPG, JPEG only, max 5MB)"
    )
    alternative_email = serializers.CharField(required=False, allow_blank=True)
    alternative_phone = serializers.CharField(required=False, allow_blank=True)

    def validate_address(self, value):
        if value and not value.strip():
            raise serializers.ValidationError("Address cannot be empty.")
        return value.strip() if value else value
    
    def validate_alternative_email(self, value):
        if not value or not value.strip():
            return None
        
        email = value.strip()
        
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            raise serializers.ValidationError("Invalid email format.")
        
        user = self.context.get('user')
        profile = self.context.get('profile')
        
        if user and user.email == email:
            raise serializers.ValidationError("This is your primary email. Use a different email as alternative.")
        
        if User.objects.filter(email=email).exclude(id=user.id).exists():
            raise serializers.ValidationError("This email is already registered as primary email by another user.")
        
        if profile:
            if StudentProfile.objects.exclude(id=profile.id).filter(alternative_emails__contains=[email]).exists():
                raise serializers.ValidationError("This email is already used as alternative email by another student.")
        else:
            if StudentProfile.objects.filter(alternative_emails__contains=[email]).exists():
                raise serializers.ValidationError("This email is already used as alternative email by another student.")
        
        if TeacherProfile.objects.filter(alternative_emails__contains=[email]).exists():
            raise serializers.ValidationError("This email is already used as alternative email by a teacher.")
        
        return email

    def validate_alternative_phone(self, value):
        if not value or not value.strip():
            return None
        
        phone = value.strip()
        
        if not re.match(r'^9[678]\d{8}$', phone):
            raise serializers.ValidationError(
                "Invalid phone number format. Must be a valid Nepali phone number (e.g., 9841234567)."
            )
        
        user = self.context.get('user')
        profile = self.context.get('profile')
        
        if user and user.phone_number == phone:
            raise serializers.ValidationError("This is your primary phone number. Use a different number as alternative.")
        
        if User.objects.filter(phone_number=phone).exclude(id=user.id).exists():
            raise serializers.ValidationError("This phone number is already registered as primary by another user.")
        
        if profile:
            if StudentProfile.objects.exclude(id=profile.id).filter(alternative_phones__contains=[phone]).exists():
                raise serializers.ValidationError("This phone number is already used as alternative by another student.")
        else:
            if StudentProfile.objects.filter(alternative_phones__contains=[phone]).exists():
                raise serializers.ValidationError("This phone number is already used as alternative by another student.")
        
        if TeacherProfile.objects.filter(alternative_phones__contains=[phone]).exists():
            raise serializers.ValidationError("This phone number is already used as alternative by a teacher.")
        
        return phone

    def update(self, instance, validated_data):
        # Update ForeignKeys
        if 'school' in validated_data:
            instance.school = validated_data['school']
        
        if 'class_level' in validated_data:
            instance.class_level = validated_data['class_level']
        
        if 'faculty' in validated_data:
            instance.faculty = validated_data['faculty']
        
        if 'address' in validated_data:
            instance.address = validated_data['address']
        
        if 'profile_image' in validated_data:
            instance.profile_image = validated_data['profile_image']
        
        # Handle alternative contacts
        if 'alternative_email' in validated_data:
            email = validated_data['alternative_email']
            if email:
                instance.alternative_emails = [email]
            else:
                instance.alternative_emails = []
        
        if 'alternative_phone' in validated_data:
            phone = validated_data['alternative_phone']
            if phone:
                instance.alternative_phones = [phone]
            else:
                instance.alternative_phones = []
        
        instance.save()
        return instance


# ============================================================================
# TEACHER PROFILE UPDATE SERIALIZER
# ============================================================================


class TeacherProfileUpdateSerializer(serializers.Serializer):
    """Update Teacher Profile with ForeignKeys"""
    
    faculty = serializers.PrimaryKeyRelatedField(
        queryset=Faculty.objects.all(),
        required=False,
        allow_null=True
    )
    
    subjects = serializers.PrimaryKeyRelatedField(
        queryset=Subject.objects.filter(is_active=True),
        many=True,
        required=False,
        help_text="List of subject IDs"
    )
    
    schools = serializers.PrimaryKeyRelatedField(
        queryset=School.objects.filter(is_verified=True),
        many=True,
        required=False,
        help_text="List of school IDs"
    )
    
    bio = serializers.CharField(required=False, allow_blank=True)
    profile_image = serializers.ImageField(
        required=False,
        allow_null=True,
        validators=[validate_image_file],
        help_text="Upload profile image (PNG, JPG, JPEG only, max 5MB)"
    )
    verification_document = serializers.FileField(
        required=False,
        allow_null=True,
        validators=[validate_verification_document],
        help_text="Upload verification document (PDF only, max 10MB)"
    )
    alternative_email = serializers.CharField(required=False, allow_blank=True)
    alternative_phone = serializers.CharField(required=False, allow_blank=True)

    def validate_alternative_email(self, value):
        if not value or not value.strip():
            return None
        
        email = value.strip()
        
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            raise serializers.ValidationError("Invalid email format.")
        
        user = self.context.get('user')
        profile = self.context.get('profile')
        
        if user and user.email == email:
            raise serializers.ValidationError("This is your primary email. Use a different email as alternative.")
        
        if User.objects.filter(email=email).exclude(id=user.id).exists():
            raise serializers.ValidationError("This email is already registered as primary email by another user.")
        
        if StudentProfile.objects.filter(alternative_emails__contains=[email]).exists():
            raise serializers.ValidationError("This email is already used as alternative email by a student.")
        
        if profile:
            if TeacherProfile.objects.exclude(id=profile.id).filter(alternative_emails__contains=[email]).exists():
                raise serializers.ValidationError("This email is already used as alternative email by another teacher.")
        else:
            if TeacherProfile.objects.filter(alternative_emails__contains=[email]).exists():
                raise serializers.ValidationError("This email is already used as alternative email by another teacher.")
        
        return email

    def validate_alternative_phone(self, value):
        if not value or not value.strip():
            return None
        
        phone = value.strip()
        
        if not re.match(r'^9[678]\d{8}$', phone):
            raise serializers.ValidationError(
                "Invalid phone number format. Must be a valid Nepali phone number (e.g., 9841234567)."
            )
        
        user = self.context.get('user')
        profile = self.context.get('profile')
        
        if user and user.phone_number == phone:
            raise serializers.ValidationError("This is your primary phone number. Use a different number as alternative.")
        
        if User.objects.filter(phone_number=phone).exclude(id=user.id).exists():
            raise serializers.ValidationError("This phone number is already registered as primary by another user.")
        
        if StudentProfile.objects.filter(alternative_phones__contains=[phone]).exists():
            raise serializers.ValidationError("This phone number is already used as alternative by a student.")
        
        if profile:
            if TeacherProfile.objects.exclude(id=profile.id).filter(alternative_phones__contains=[phone]).exists():
                raise serializers.ValidationError("This phone number is already used as alternative by another teacher.")
        else:
            if TeacherProfile.objects.filter(alternative_phones__contains=[phone]).exists():
                raise serializers.ValidationError("This phone number is already used as alternative by another teacher.")
        
        return phone

    def update(self, instance, validated_data):
          
        
        if 'faculty' in validated_data:
            instance.faculty = validated_data['faculty']

        if 'subjects' in validated_data:
            instance.subjects.set(validated_data['subjects'])
        
        if 'schools' in validated_data:
            # Clear existing school affiliations
            instance.teacher_schools.all().delete()
            
            # Add new school affiliations
            for school in validated_data['schools']:
                TeacherSchool.objects.create(
                    teacher=instance,
                    school=school
                )
        
        if 'bio' in validated_data:
            instance.bio = validated_data['bio']
        
        if 'profile_image' in validated_data:
            instance.profile_image = validated_data['profile_image']
        
        if 'verification_document' in validated_data:
            instance.verification_document = validated_data['verification_document']
        
        # Handle alternative contacts
        if 'alternative_email' in validated_data:
            email = validated_data['alternative_email']
            if email:
                instance.alternative_emails = [email]
            else:
                instance.alternative_emails = []
        
        if 'alternative_phone' in validated_data:
            phone = validated_data['alternative_phone']
            if phone:
                instance.alternative_phones = [phone]
            else:
                instance.alternative_phones = []
        
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
        validators=[validate_nepali_phone_number]
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
        allow_blank=True,   
        allow_null=True,
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
        
        validate_nepali_phone_number(phone_number)
        
        return data


class LoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField(
        max_length=10,
        validators=[validate_nepali_phone_number]
    )
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

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


# ============================================================================
# PASSWORD RESET SERIALIZERS
# ============================================================================

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
            self.fields['phone_number'].required = False
            self.fields['phone_number'].help_text = "Not required for authenticated users"
            self.fields['old_password'].required = True
            self.fields['new_password'].required = True
            self.fields['confirm_password'].required = True
        else:
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

        if user and user.is_authenticated:
            old_password = attrs.get("old_password")
            new_password = attrs.get("new_password")
            confirm_password = attrs.get("confirm_password")

            if not old_password:
                raise serializers.ValidationError({
                    "old_password": "Old password is required to change your password."
                })

            if not new_password:
                raise serializers.ValidationError({
                    "new_password": "New password is required."
                })

            if not confirm_password:
                raise serializers.ValidationError({
                    "confirm_password": "Please confirm your new password."
                })

            if new_password != confirm_password:
                raise serializers.ValidationError({
                    "confirm_password": "Passwords do not match."
                })

            if not user.check_password(old_password):
                raise serializers.ValidationError({
                    "old_password": "Old password is incorrect."
                })

            if old_password == new_password:
                raise serializers.ValidationError({
                    "new_password": "New password must be different from the old password."
                })

            try:
                validate_password(new_password)
            except ValidationError as e:
                raise serializers.ValidationError({
                    "new_password": list(e.messages)
                })

            if attrs.get("phone_number"):
                raise serializers.ValidationError({
                    "phone_number": "Phone number is not required for authenticated users."
                })

            return attrs

        else:
            phone_number = attrs.get("phone_number")

            if not phone_number:
                raise serializers.ValidationError({
                    "phone_number": "Phone number is required to reset your password."
                })

            if not User.objects.filter(phone_number=phone_number, is_active=True).exists():
                raise serializers.ValidationError({
                    "phone_number": "No active account found with this phone number."
                })

            if attrs.get("old_password"):
                raise serializers.ValidationError({
                    "old_password": "Old password is not required for password reset."
                })

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


# ============================================================================
# ADMIN SERIALIZERS
# ============================================================================

class AdminUserSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    middle_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150)
    phone_number = serializers.CharField(
        max_length=10,
        validators=[validate_nepali_phone_number]
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

class TokenRefreshSerializer(serializers.Serializer):
    """Serializer for token refresh request"""
    refresh = serializers.CharField(required=True, help_text="Refresh token")