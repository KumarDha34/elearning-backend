from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import (
    School, Faculty, ClassLevel, Subject, TeacherSchool,Chapter
)


class SchoolSerializer(serializers.ModelSerializer):
    """Serializer for School model"""
    created_by_name = serializers.SerializerMethodField()
    is_verified_display = serializers.SerializerMethodField()
    
    class Meta:
        model = School
        fields = [
            'id', 'name', 'address', 'school_type', 
            'is_verified', 'is_verified_display',
            'created_by', 'created_by_name', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']
    
    @extend_schema_field(serializers.CharField())
    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name()
        return None
    
    @extend_schema_field(serializers.CharField())
    def get_is_verified_display(self, obj):
        return 'Verified' if obj.is_verified else 'Pending Verification'


class FacultySerializer(serializers.ModelSerializer):
    """Serializer for Faculty model"""
    
    class Meta:
        model = Faculty
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class ClassLevelSerializer(serializers.ModelSerializer):
    """Serializer for ClassLevel model"""
    level_type_display = serializers.SerializerMethodField()
    
    class Meta:
        model = ClassLevel
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']
    
    @extend_schema_field(serializers.CharField())
    def get_level_type_display(self, obj):
        return obj.get_level_type_display()


class SubjectSerializer(serializers.ModelSerializer):
    """Serializer for Subject model"""
    faculty_name = serializers.CharField(source='faculty.name', read_only=True)
    class_level_name = serializers.CharField(source='class_level.name', read_only=True)
    
    class Meta:
        model = Subject
        fields = [
            'id', 'name', 'faculty', 'faculty_name',
            'class_level', 'class_level_name', 
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class TeacherSchoolSerializer(serializers.ModelSerializer):
    """Serializer for TeacherSchool model"""
    teacher_name = serializers.SerializerMethodField()
    school_name = serializers.CharField(source='school.name', read_only=True)
    
    class Meta:
        model = TeacherSchool
        fields = [
            'id', 'teacher', 'teacher_name', 
            'school', 'school_name', 'joined_at'
        ]
        read_only_fields = ['joined_at']
    
    @extend_schema_field(serializers.CharField())
    def get_teacher_name(self, obj):
        return obj.teacher.user.get_full_name()
    
class ChapterSerializer(serializers.ModelSerializer):
    subject_name=serializers.CharField(source='subject.name',read_only=True)

    class Meta:
        model=Chapter
        fields=[
            'id','subject','subject_name',
            'name','description','is_active','created_at','updated_at'
        ]
        read_only_fields=['created_at','updated_at']

    def validate_name(self,value):
        if not value or not value.strip():
            raise serializers.ValidationError("Chapter name cannot be empty")
        if len(value.strip())<2:
            raise serializers.ValidationError("Chapter name must be at least 2 characters")
        return value.strip()

    def validate_subject(self,value):
        if not value:
            raise serializers.ValidationError("Subject is required")
        if not value.is_active:
            raise serializers.ValidationError("Cannot create chapter for an return value")