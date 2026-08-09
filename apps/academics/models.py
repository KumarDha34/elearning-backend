from django.db import models
from django.conf import settings
from django.utils import timezone


class School(models.Model):
    """School/Colleges/Universities in Nepal"""
    class SchoolType(models.TextChoices):
        SCHOOL = 'School', 'School'
        COLLEGE = 'College', 'College'
        UNIVERSITY = 'University', 'University'

    name=models.CharField(max_length=255,verbose_name="School Name")
    address=models.CharField(max_length=255,verbose_name="School Address (Kalanki,Kathmandu)")
    school_type=models.CharField(max_length=20,choices=SchoolType.choices,default=SchoolType.SCHOOL,verbose_name="School Type")
    is_verified=models.BooleanField(default=False,verbose_name="Is Verified")
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name='created_schools')
    created_at=models.DateTimeField(auto_now_add=True,verbose_name='Created AT')
    updated_at=models.DateTimeField(auto_now=True,verbose_name='updated at')

    class Meta:
        db_table = 'schools'
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['school_type']),
        ]
        verbose_name = 'School'
        verbose_name_plural = 'Schools'

    def __str__(self):
        return self.name

class Faculty(models.Model):
    """Academic faculties - Science, Management, Arts, Education, etc."""
    
    name = models.CharField(max_length=100, unique=True, verbose_name='Faculty Name')
    description = models.TextField(blank=True, null=True, verbose_name='Description')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created At')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated At')

    class Meta:
        db_table = 'faculties'
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
        ]
        verbose_name = 'Faculty'
        verbose_name_plural = 'Faculties'

    def __str__(self):
        return self.name

class ClassLevel(models.Model):
    """Class levels 10 ,11, 12, Bachelor, Master"""
    
    class LevelType(models.TextChoices):
        SEE = 'SEE', 'SEE (Grade 10)'
        PLUS_TWO = '+2', '+2 (Grade 11-12)'
        BACHELOR = 'bachelor', 'Bachelor'
    
    name = models.CharField(max_length=50, verbose_name='Class Name')
    level_type = models.CharField(
        max_length=20,
        choices=LevelType.choices,
        verbose_name='Level Type'
    )
    display_order = models.IntegerField(default=0, verbose_name='Display Order')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created At')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated At')

    class Meta:
        db_table = 'class_levels'
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['level_type']),
            models.Index(fields=['display_order']),
        ]
        verbose_name = 'Class Level'
        verbose_name_plural = 'Class Levels'

    def __str__(self):
        return self.name

class Subject(models.Model):
    """Subjects linked to faculty and class level"""
    
    name = models.CharField(max_length=100, verbose_name='Subject Name')
    faculty = models.ForeignKey(
        Faculty,
        on_delete=models.CASCADE,
        related_name='subjects',
        verbose_name='Faculty'
    )
    class_level = models.ForeignKey(
        ClassLevel,
        on_delete=models.CASCADE,
        related_name='subjects',
        verbose_name='Class Level'
    )
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created At')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated At')

    class Meta:
        db_table = 'subjects'
        ordering = ['name']
        indexes = [
            models.Index(fields=['faculty', 'class_level']),
            models.Index(fields=['name']),
        ]
        unique_together = [['faculty', 'class_level', 'name']]
        verbose_name = 'Subject'
        verbose_name_plural = 'Subjects'

    def __str__(self):
        return self.name

class Chapter(models.Model):
    """Chapters within a subject"""
    
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='chapters',
        verbose_name='Subject'
    )
    name = models.CharField(max_length=200, verbose_name='Chapter Name')
    description = models.TextField(blank=True, null=True, verbose_name='Description')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created At')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated At')

    class Meta:
        db_table = 'chapters'
        ordering = ['subject', 'id']
        indexes = [
            models.Index(fields=['subject']),
            models.Index(fields=['name']),
        ]
        verbose_name = 'Chapter'
        verbose_name_plural = 'Chapters'

    def __str__(self):
        return f"{self.name}"


class TeacherSchool(models.Model):
    """Teachers can be affiliated with multiple schools"""
    
    teacher = models.ForeignKey(
        'accounts.TeacherProfile',
        on_delete=models.CASCADE,
        related_name='teacher_schools',
        verbose_name='Teacher'
    )
    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name='teacher_schools',
        verbose_name='School'
    )
    joined_at = models.DateTimeField(auto_now_add=True, verbose_name='Joined At')

    class Meta:
        db_table = 'teacher_schools'
        ordering = ['-joined_at']
        unique_together = [['teacher', 'school']]
        indexes = [
            models.Index(fields=['teacher', 'school']),
        ]
        verbose_name = 'Teacher School'
        verbose_name_plural = 'Teacher Schools'

    def __str__(self):
        return f"{self.teacher.user.get_full_name()} @ {self.school.name}"