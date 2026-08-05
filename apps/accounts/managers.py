from django.contrib.auth.base_user import BaseUserManager
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
       
    def create_user(self, phone, role, password=None, **extra_fields):
       
        if not phone:
            raise ValueError(_('The Phone number must be set'))
        if not role:
            raise ValueError(_('Role must be set'))
                
        phone = ''.join(filter(str.isdigit, phone))
        user = self.model(phone=phone, role=role, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', 'admin')
        extra_fields.setdefault('phone_verified', True)
        
        
        if 'role' in extra_fields:
           extra_fields.pop('role')
        
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        # if extra_fields.get('role') != 'admin':
        #     raise ValueError(_('Superuser must have role=admin.'))
        
        return self.create_user(phone, 'admin', password, **extra_fields)
    
    
    def create_student(self, phone, password=None, **extra_fields):
        extra_fields.setdefault('role', 'student')
        return self.create_user(phone, 'student', password, **extra_fields)
    
    
    def create_instructor(self, phone, password=None, **extra_fields):
        extra_fields.setdefault('role', 'instructor')
        return self.create_user(phone, 'instructor', password, **extra_fields)