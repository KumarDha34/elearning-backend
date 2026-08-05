from rest_framework import serializers
from .models import *
from .services import OTPService


class Phase1SignupSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=15)
    middle_name = serializers.CharField(max_length=15)
    last_name = serializers.CharField(max_length=15)
    phone = serializers.CharField(max_length=15)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICE)
    
    
    def validate_phone(self, value):
        value = ''.join(filter(str.isdigit, value))
        if len(value) != 10:
            raise serializers.ValidationError("Phone must be 10 digits")
        if not value.startswith(('98', '97')):
            raise serializers.ValidationError("Phone must start with 98 or 97")
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("User already exists")
        return value

    
    def create(self, validated_data):
        # Store in temporary table
        temp_data = TempUserData.objects.create(
            phone=validated_data['phone'],
            role=validated_data['role'],
            first_name=validated_data['first_name'],
            middle_name=validated_data.get('middle_name', ''),
            last_name=validated_data['last_name']
        )
        return temp_data


class OTPRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)
    purpose = serializers.ChoiceField(choices=['signup', 'password_reset'], default='signup')
    
    def validate_phone(self, value):
        value = ''.join(filter(str.isdigit, value))
        if len(value) != 10:
            raise serializers.ValidationError("Phone must be 10 digits")
        return value


class OTPVerifySerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)
    otp = serializers.CharField(max_length=6)
    purpose = serializers.ChoiceField(choices=['signup', 'password_reset'], default='signup')
    
    def validate(self, data):
        
        phone = ''.join(filter(str.isdigit, data['phone']))
        result = OTPService.verify_otp(phone, data['otp'], 
        data['purpose'])
        if not result['success']:
            raise serializers.ValidationError(result['message'])
        data['phone'] = phone
        return data
    
    
class StudentPhase2Serializer(serializers.Serializer):
    """
    Phase 2: Complete profile with email, address, college, class, password
    """
    # phone = serializers.CharField(max_length=15)
    email = serializers.EmailField()
    address = serializers.CharField(max_length=500)
    college_school = serializers.CharField(max_length=255)
    class_level = serializers.CharField(max_length=50)
    faculty = serializers.CharField(max_length=100)
    password = serializers.CharField(min_length=8, write_only=True)
    confirm_password = serializers.CharField(min_length=8, write_only=True)
    
    def validate_phone(self, value):
        value = ''.join(filter(str.isdigit, value))
        if len(value) != 10:
            raise serializers.ValidationError("Phone must be 10 digits")
        
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("User already registered")
        
        if not TempUserData.objects.filter(phone=value).exists():
            raise serializers.ValidationError("Please complete phase 1 registration first")
        
        return value
    
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already registered")
        return value
    
    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords don't match"})
        return data
    
    def save(self):
        phone = self.validated_data['phone']
        temp_data = TempUserData.objects.get(phone=phone)
        
        user = User.objects.create_user(
            phone=phone,
            role=temp_data.role,
            password=self.validated_data['password'],
            first_name=temp_data.first_name,
            middle_name=temp_data.middle_name,
            last_name=temp_data.last_name,
            email=self.validated_data['email'],
            address=self.validated_data['address'],
            college_school=self.validated_data['college_school'],
            class_level=self.validated_data['class_level'],
            faculty=self.validated_data['faculty'],
            phone_verified=True,
            is_active=True
        )
        
        temp_data.delete()
        return user


class TeacherPhase2Serializer(serializers.Serializer):
    
    phone = serializers.CharField(max_length=15)
    email = serializers.EmailField()
    faculty = serializers.CharField(max_length=100)
    subjects = serializers.ListField(
        child=serializers.CharField(max_length=100),
        min_length=1,
        help_text="List of subjects"
    )
    schools = serializers.ListField(
        child=serializers.CharField(max_length=255),
        min_length=1,
        help_text="List of schools/colleges"
    )
    password = serializers.CharField(min_length=8, write_only=True)
    confirm_password = serializers.CharField(min_length=8, write_only=True)
    
    def validate_phone(self, value):
        value = ''.join(filter(str.isdigit, value))
        if len(value) != 10:
            raise serializers.ValidationError("Phone must be 10 digits")
        
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("User already registered")
        
        if not TempUserData.objects.filter(phone=value).exists():
            raise serializers.ValidationError("Please complete phase 1 registration first")
        
        # Verify it's a teacher
        temp_data = TempUserData.objects.get(phone=value)
        if temp_data.role != 'instructor':
            raise serializers.ValidationError("This phone is registered as a student, not a teacher")
        
        return value
    
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already registered")
        return value
    
    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords don't match"})
        return data
    
    def save(self):
        phone = self.validated_data['phone']
        temp_data = TempUserData.objects.get(phone=phone)
        
        # Convert lists to comma-separated strings
        subjects_str = ', '.join(self.validated_data['subjects'])
        schools_str = ', '.join(self.validated_data['schools'])
        
        user = User.objects.create_user(
            phone=phone,
            role=temp_data.role,
            password=self.validated_data['password'],
            first_name=temp_data.first_name,
            middle_name=temp_data.middle_name,
            last_name=temp_data.last_name,
            email=self.validated_data['email'],
            faculty=self.validated_data['faculty'],
            subjects=subjects_str,
            schools=schools_str,
            phone_verified=True,
            is_active=True
        )
        
        temp_data.delete()
        return user



class LoginSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)
    password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        phone = ''.join(filter(str.isdigit, data['phone']))
        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid credentials")
        
        if not user.check_password(data['password']):
            raise serializers.ValidationError("Invalid credentials")
        if not user.is_active:
            raise serializers.ValidationError("Account is deactivated")
        if not user.phone_verified:
            raise serializers.ValidationError("Phone not verified. Please complete signup.")
        
        data['user'] = user
        return data


class PasswordResetConfirmSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)
    new_password = serializers.CharField(min_length=8, write_only=True)
    confirm_password = serializers.CharField(min_length=8, write_only=True)
    
    def validate_phone(self, value):
        value = ''.join(filter(str.isdigit, value))
        if len(value) != 10:
            raise serializers.ValidationError("Phone must be 10 digits")
        return value
    
    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords don't match"})
        return data
    
    def save(self):
        phone = self.validated_data['phone']
        try:
            user = User.objects.get(phone=phone)
            user.set_password(self.validated_data['new_password'])
            user.save()
            return user
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'id', 'phone', 'username', 'role', 'phone_verified', 'class_level', 'faculty','college_school','address',
            'first_name', 'middle_name', 'last_name', 'email',
            'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'username', 'phone_verified', 'created_at', 'updated_at')
    
    def update(self, instance, validated_data):
        allowed_fields = ['first_name', 'middle_name', 'last_name', 'email']
        for field in allowed_fields:
            if field in validated_data:
                setattr(instance, field, validated_data[field])
        instance.save()
        return instance