from django.contrib import admin

from .models import BlogCategory, BlogPost, BlogComment, BlogLike, TeacherFollow


@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'created_at')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'uploaded_by', 'category', 'status', 'views', 'likes_count', 'published_at')
    list_filter = ('status', 'category')
    search_fields = ('title', 'description', 'content')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('views', 'likes_count', 'comments_count', 'created_at', 'updated_at')


@admin.register(BlogComment)
class BlogCommentAdmin(admin.ModelAdmin):
    list_display = ('author', 'post', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('content',)


@admin.register(BlogLike)
class BlogLikeAdmin(admin.ModelAdmin):
    list_display = ('user', 'post', 'created_at')


@admin.register(TeacherFollow)
class TeacherFollowAdmin(admin.ModelAdmin):
    list_display = ('student', 'teacher', 'created_at')