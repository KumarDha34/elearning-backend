from rest_framework import serializers
from .models import User
from .services import OTPService


class SignupSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICE)
    password = serializers.CharField(min_length=8, write_only=True)
    confirm_password = serializers.CharField(min_length=8, write_only=True)
    
    def validate_phone(self, value):
        value = ''.join(filter(str.isdigit, value))
        if len(value) != 10:
            raise serializers.ValidationError("Phone must be 10 digits")
        if not value.startswith(('98', '97')):
            raise serializers.ValidationError("Phone must start with 98 or 97")
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("User already exists")
        return value
    
    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords don't match"})
        return data
    
    def create(self, validated_data):
        validated_data.pop('confirm_password')
        return User.objects.create_user(
            phone=validated_data['phone'],
            role=validated_data['role'],
            password=validated_data['password']
        )


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
        result = OTPService.verify_otp(phone, data['otp'], data['purpose'])
        if not result['success']:
            raise serializers.ValidationError(result['message'])
        data['phone'] = phone
        return data


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
            'id', 'phone', 'username', 'role', 'phone_verified',
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