from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    # ── Categories ──
    path('categories/', views.BlogCategoryListCreateView.as_view(), name='category-list-create'),
    path('categories/<int:pk>/', views.BlogCategoryDetailView.as_view(), name='category-detail'),

    path('posts/', views.BlogPostPublicListView.as_view(), name='post-public-list'),
    path('posts/create/', views.BlogPostCreateView.as_view(), name='post-create'),       
    path('posts/my/', views.BlogPostMyListView.as_view(), name='post-my-list'),

    path('posts/<int:pk>/reject/', views.BlogPostRejectView.as_view(), name='post-reject'),
    path('posts/<int:pk>/like/', views.ToggleBlogLikeView.as_view(), name='post-like'),
    path('posts/<int:pk>/comments/', views.BlogCommentCreateView.as_view(), name='comment-create'),

    path('posts/<slug:slug>/', views.BlogPostDetailView.as_view(), name='post-detail'),  

    # ── Follow ──
    path('teachers/<int:pk>/follow/', views.ToggleTeacherFollowView.as_view(), name='teacher-follow-toggle'),

    # ── Feed ──
    path('feed/', views.FeedView.as_view(), name='feed'),
    path('my-liked-posts/', views.MyLikedPostsView.as_view(), name='my-liked-posts'),
]