from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    # Categories (2 URL patterns, 5 methods)
    path('categories/', views.BlogCategoryListCreateView.as_view(), name='category-list-create'),
    path('categories/<int:pk>/', views.BlogCategoryDetailView.as_view(), name='category-detail'),

    path('posts/', views.BlogPostListCreateView.as_view(), name='post-list-create'),
    path('posts/<slug:slug>/', views.BlogPostDetailView.as_view(), name='post-detail'),
    path('posts/<int:pk>/edit/', views.BlogPostUpdateView.as_view(), name='post-update'),
    path('posts/<int:pk>/delete/', views.BlogPostDeleteView.as_view(), name='post-delete'),
    path('posts/<int:pk>/like/', views.ToggleBlogLikeView.as_view(), name='post-like'),

    path('posts/<int:pk>/comments/', views.BlogCommentCreateView.as_view(), name='comment-create'),

    path('teachers/<int:pk>/follow/', views.TeacherFollowView.as_view(), name='teacher-follow'),

    path('feed/', views.FeedView.as_view(), name='feed'),
    path('my-liked-posts/', views.MyLikedPostsView.as_view(), name='my-liked-posts'),

]