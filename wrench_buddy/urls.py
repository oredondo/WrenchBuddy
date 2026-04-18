from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from users.views import csrf
from social.views import GarageListView, GarageDetailView

urlpatterns = [
    path('admin/', admin.site.urls),
    # API endpoints
    path('api/users/', include('users.urls')),
    path('api/vehicles/', include('vehicles.urls')),
    path('api/maintenance/', include('maintenance.urls')),
    path('api/ai/', include('ai_assistant.urls')),
    path('api/social/', include('social.urls')),
    path('api/garage/', GarageListView.as_view(), name='garage-list'),
    path('api/garage/<str:username>/', GarageDetailView.as_view(), name='garage-detail'),
    path('api-auth/', include('rest_framework.urls')),
    path("api/csrf/", csrf),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
