from django.contrib.auth.base_user import BaseUserManager
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    """Custom user manager with phone as username"""

    def _create_user(self, phone_number, password=None, **extra_fields):
        """Create and save a user with the given phone number and password."""
        if not phone_number:
            raise ValueError(_('Phone number is required'))
        
        phone_number = ''.join(filter(str.isdigit, phone_number))
        extra_fields.setdefault('is_active', True)
        
        user = self.model(phone_number=phone_number, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.password=None 
        user.save(using=self._db)
        return user

    def create_user(self, phone_number, password=None, **extra_fields):
        """Create a regular user."""
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        extra_fields.setdefault('role', 'student')
        extra_fields.setdefault('signup_step', 1)
        extra_fields.setdefault('profile_completed', False)
        extra_fields.setdefault('phone_verified', False)
        return self._create_user(phone_number, password, **extra_fields)

    def create_superuser(self, phone_number, password=None, **extra_fields):
        """Create a superuser (Admin)."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')
        extra_fields.setdefault('phone_verified', True)
        extra_fields.setdefault('profile_completed', True)
        extra_fields.setdefault('signup_step', 3)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self._create_user(phone_number, password, **extra_fields)

    def create_editor(self, phone_number, password=None, **extra_fields):
        """Create an editor user."""
        extra_fields.setdefault('role', 'editor')
        extra_fields.setdefault('phone_verified', True)
        extra_fields.setdefault('profile_completed', True)
        extra_fields.setdefault('signup_step', 3)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(phone_number, password, **extra_fields)