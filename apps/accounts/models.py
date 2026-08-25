from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from .managers import UserManager
from django.utils.translation import gettext_lazy as _
from .validators import validate_nepali_phone_number

class User(AbstractUser):
    """Custom User Model with phone as primary identifier"""
    
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        STUDENT = 'student', 'Student'
        INSTRUCTOR = 'instructor', 'Instructor'
        EDITOR = 'editor', 'Editor'

    # Core fields
    first_name = models.CharField(max_length=150)
    middle_name = models.CharField(max_length=150, blank=True, null=True)
    last_name = models.CharField(max_length=150)
    
    # Phone as primary identifier
    phone_number = models.CharField(
        max_length=10,
        unique=True,
        validators=[validate_nepali_phone_number],
        db_index=True,
        verbose_name='Phone Number'
    )
    
    # Role and status
    password = models.CharField(max_length=200, blank=True, null=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    phone_verified = models.BooleanField(default=False)
    profile_completed = models.BooleanField(default=False)
    signup_step = models.PositiveSmallIntegerField(default=1)  # 1=basic, 2=otp, 3=profile
    
    # Auto-generated username
    username = models.CharField(max_length=30, unique=True, null=True, blank=True)
    
    # Email (optional)
    email = models.EmailField(unique=True, null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    
    objects = UserManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        db_table = 'users'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone_number', 'is_active']),
            models.Index(fields=['role', 'is_active']),
            models.Index(fields=['signup_step']),
        ]

    def __str__(self):
        return f"{self.get_full_name()} ({self.phone_number})"

    def get_full_name(self):
        name_parts = [self.first_name]
        if self.middle_name:
            name_parts.append(self.middle_name)
        name_parts.append(self.last_name)
        return ' '.join(name_parts)

    def generate_username(self):
        """Auto-generate username: first+last initial + last 4 digits of phone"""
        if not self.first_name or not self.last_name or not self.phone_number:
            return
        
        first_letter = self.first_name[0].upper()
        last_letter = self.last_name[0].upper()
        last_four_digits = self.phone_number[-4:]
        
        base_username = f'{first_letter}{last_letter}{last_four_digits}'
        
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exclude(id=self.id).exists():
            username = f'{base_username}{counter}'
            counter += 1
        
        self.username = username

    def save(self, *args, **kwargs):
        if not self.username:
            self.generate_username()
        super().save(*args, **kwargs)

    # Role helpers
    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN or self.is_superuser
    
    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    @property
    def is_instructor(self):
        return self.role == self.Role.INSTRUCTOR

    @property
    def is_editor(self):
        return self.role == self.Role.EDITOR

    @property
    def is_verified_teacher(self):
        """Check if teacher is verified (document approved)"""
        if not self.is_instructor:
            return False
        if hasattr(self, 'teacher_profile'):
            return self.teacher_profile.status == 'verified'
        return False


class OTPVerification(models.Model):
    """OTP Verification model"""
    
    class Purpose(models.TextChoices):
        SIGNUP = 'signup', 'Signup'
        LOGIN = 'login', 'Login'
        PASSWORD_RESET = 'password_reset', 'Password Reset'

    phone_number = models.CharField(
        max_length=10,
        validators=[validate_nepali_phone_number],
        db_index=True
    )
    otp_code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=20, choices=Purpose.choices, default=Purpose.SIGNUP)
    
    is_verified = models.BooleanField(default=False)
    is_used = models.BooleanField(default=False)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=5)
    
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'otp_verifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone_number', 'purpose', 'is_verified']),
            models.Index(fields=['expires_at', 'is_used']),
        ]

    def __str__(self):
        return f"OTP for {self.phone_number} - {'Verified' if self.is_verified else 'Pending'}"

    def is_expired(self):
        return timezone.now() > self.expires_at

    def is_exhausted(self):
        return self.attempt_count >= self.max_attempts

    def is_valid(self):
        return (not self.is_used and 
                not self.is_verified and 
                not self.is_expired() and 
                not self.is_exhausted())

    def increment_attempts(self):
        self.attempt_count += 1
        if self.attempt_count >= self.max_attempts:
            self.is_used = True
        self.save(update_fields=['attempt_count', 'is_used'])

    def mark_verified(self):
        self.is_verified = True
        self.is_used = True
        self.verified_at = timezone.now()
        self.save(update_fields=['is_verified', 'is_used', 'verified_at'])

    def save(self, *args, **kwargs):
        if not self.expires_at and self.created_at:
            from django.conf import settings
            self.expires_at = self.created_at + timezone.timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
        super().save(*args, **kwargs)


class StudentProfile(models.Model):
    """Student Profile model"""
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='student_profile'
    )
    school = models.ForeignKey(
        'academics.School',  
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("School/College"),
        related_name='student_profiles')
    
    
    school_type = models.CharField(
        max_length=20,
        choices=[('school', 'School'), ('college', 'College'), ('university', 'university')],
        default='school'
    )
    class_level = models.ForeignKey('academics.ClassLevel', verbose_name=_("class_level"), on_delete=models.SET_NULL, null=True,)
    faculty =models.ForeignKey('academics.Faculty', verbose_name=_("faculty"), on_delete=models.SET_NULL, null=True,)
    address = models.CharField(
            max_length=200, 
            verbose_name='Address',
            help_text='e.g., Kalanki, Kathmandu'
        )    
    email = models.EmailField(verbose_name='Email')
    profile_image = models.ImageField(upload_to="images/student", null=True, blank= True)

    alternative_emails = models.JSONField(
        default=list,
        blank=True,
        help_text='List of alternative email addresses'
    )
    alternative_phones = models.JSONField(
        default=list,
        blank=True,
        help_text='List of alternative phone numbers'
    )
    
    points_balance = models.IntegerField(default=0, verbose_name='Points Balance')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'student_profiles'
        verbose_name = 'Student Profile'

    def __str__(self):
        return f"Student: {self.user.get_full_name()}"


class TeacherProfile(models.Model):
    """Teacher Profile model"""

    class Status(models.TextChoices):
        NOT_VERIFIED = 'not_verified', 'Not Verified'
        VERIFIED = 'verified', 'Verified'
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='teacher_profile'
    )
    
    faculty =models.ForeignKey('academics.Faculty', verbose_name=_("faculty"), on_delete=models.SET_NULL, null=True,)
    subjects = models.ManyToManyField('academics.Subject', verbose_name=_("Subjects"), related_name='teachers', blank=True, help_text=_("Subjects taught by the teacher"))    
    # schools = models.ManyToManyField('academics.School', verbose_name=_("Schools/Colleges"), related_name='teacher_profiles', blank=True, help_text=_("Schools/Colleges the teacher is associated with"))    
    email = models.EmailField(verbose_name='Email')
    profile_image = models.ImageField(upload_to="images/teachers", null=True, blank= True)
    alternative_emails = models.JSONField(
        default=list,
        blank=True,
        help_text='List of alternative email addresses'
    )
    alternative_phones = models.JSONField(
        default=list,
        blank=True,
        help_text='List of alternative phone numbers'
    )
    
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=0.00, verbose_name='Average Rating')
    content_limit = models.IntegerField(default=50, verbose_name='Content Limit')
    content_count = models.IntegerField(default=0, verbose_name='Content Count')
    bio = models.TextField(blank=True, verbose_name='Biography')
    verification_document = models.FileField(
            upload_to='images/teacher_verification',
            null=True,
            blank=True,
            verbose_name='Verification Document'
        )    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NOT_VERIFIED,
        verbose_name='Verification Status'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'teacher_profiles'
        verbose_name = 'Teacher Profile'

    def __str__(self):
        return f"Teacher: {self.user.get_full_name()}"

    def can_perform_operations(self):
        """Check if teacher can perform content operations"""
        return self.status == self.Status.VERIFIED
    
    @property
    def schools(self):
        """Get all schools for this teacher through TeacherSchool"""
        return [ts.school for ts in self.teacher_schools.all()]