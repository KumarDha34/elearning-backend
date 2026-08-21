from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from django.conf.urls.static import static 
from django.conf import settings


urlpatterns = [
    path("admin/", admin.site.urls),
    # path("api/v1/auth/", include("apps.accounts.urls")),
    # OpenAPI schema & interactive docs
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    # path("api/v1/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    
     path('api/v1/docs/', SpectacularSwaggerView.as_view(
        template_name='swagger_ui.html'
    ), name='swagger-ui'),
    
    #API v1
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/academics/', include('apps.academics.urls')),
    path('api/v1/notes/', include('apps.notes.urls')),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


