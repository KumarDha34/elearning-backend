# apps/ads/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

app_name = 'ads'

router = DefaultRouter()
router.register(r'ads', views.AdCampaignViewSet, basename='adcampaign')

urlpatterns = [
    # 1. Custom paths MUST come first so the router doesn't swallow them
    path('ads/feed/', views.AdFeedView.as_view(), name='ads-feed'),
    
    path(
        'ads/<int:pk>/impression/', 
        views.AdInteractionView.as_view(), 
        {'action_type': 'impression'}, 
        name='ads-impression'
    ),
    path(
        'ads/<int:pk>/click/', 
        views.AdInteractionView.as_view(), 
        {'action_type': 'click'}, 
        name='ads-click'
    ),

    # 2. The router goes LAST
    path('', include(router.urls)),
]