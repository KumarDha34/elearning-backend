from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from .managers import UserManager
# Create your models here.

class User(AbstractUser):
    
    
    ROLE_CHOICE = (
        ('student', 'student'),
        ('instructor', 'instructor'),
        ('admin', 'admin'),
        
    )
    
    phone = models.CharField(max_length=15, unique=True, help_text= "e.g., 9877676543")
    role = models.CharField(max_length=10, choices=ROLE_CHOICE)
    first_name = models.CharField(max_length=20, blank=True)
    middle_name = models.CharField(max_length=20, blank=True)
    last_name = models.CharField(max_length=20, blank=True)
    phone_verified = models.BooleanField(default=False)
    
    email = models.EmailField(blank=True, unique=True, null=True)
    address = models.TextField(blank=True, help_text="Permanent address")
    college_school = models.CharField(max_length=255, blank=True, help_text="College or School name")
    class_level = models.CharField(max_length=50, blank=True, help_text="e.g., Class 12, BSc 1st Year")
    
    username = models.CharField(max_length=20, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = ['role']
    
    class Meta:
        db_table = 'users'
        indexes = [
            models.Index(fields=['phone']),
            models.Index(fields=['role']),
        ]
        
    def __str__(self):
        return f"{self.username or self.phone} ({self.role})"
    
    
    def save(self, *args, **kwargs):
        if not self.username:
            
            first_letter = self.first_name[0].lower() if self.first_name else 'u'
            last_letter = self.last_name[0].lower() if self.last_name else 'id'
            
            base_username = f"{first_letter}{last_letter}"
            username = f"{base_username}{self.phone[-4:]}"
            
            
            counter = 1
            while User.objects.filter(username=username).exclude(pk=self.pk).exists():
                username = f"{base_username}{self.phone[-4:]}_{counter}"
                counter += 1
                
            self.username = username
            
        super().save(*args, **kwargs)
        
        
    @property
    def is_admin(self):
        return self.is_superuser or self.is_staff
    
    @property
    def is_editor(self):
        return self.is_staff and self.has_perm('notes.can_approve_notes') #feedback needed for now only aproval
    

    @property
    def is_instructor(self):
        return self.role == 'instructor'
    
    @property
    def is_student(self):
        return self.role == 'student'
    
class OTPVerification(models.Model):
   
    
    PURPOSE_CHOICES = (
        ('signup', 'Signup'),
        ('password_reset', 'Password Reset'),
    )
    
    phone = models.CharField(max_length=15)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    attempts = models.IntegerField(default=0)
    verified = models.BooleanField(default=False)
    purpose = models.CharField(
        max_length=20,
        default='signup',
        choices=PURPOSE_CHOICES
    )
    
    class Meta:
        db_table = 'otp_verifications'
        indexes = [
            models.Index(fields=['phone', 'verified']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"OTP for {self.phone} - {'Verified' if self.verified else 'Pending'}"
    
    def is_expired(self):
        from datetime import timedelta
        expiry_time = self.created_at + timedelta(minutes=5)
        return timezone.now() > expiry_time
    
    def increment_attempts(self):
        self.attempts += 1
        self.save(update_fields=['attempts'])
        return self.attempts
    
    def can_retry(self, max_attempts=5):
        return self.attempts < max_attempts
    
class TempUserData(models.Model):

#need to store the data temporarily as first part data is not yet stored    
    phone = models.CharField(max_length=15, unique=True)
    role = models.CharField(max_length=10)
    first_name = models.CharField(max_length=20)
    middle_name = models.CharField(max_length=20, blank=True)
    last_name = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'temp_user_data'
    
    def __str__(self):
        return f"Temp: {self.first_name} {self.last_name} ({self.phone})"