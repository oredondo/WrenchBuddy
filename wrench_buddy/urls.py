from django.contrib import admin
from django.urls import path, include
from users.views import csrf

urlpatterns = [
    path('admin/', admin.site.urls),
    # API endpoints
    path('api/users/', include('users.urls')),
    path('api/vehicles/', include('vehicles.urls')),
    path('api/maintenance/', include('maintenance.urls')),
    path('api-auth/', include('rest_framework.urls')),
    path("api/csrf/", csrf),
]
