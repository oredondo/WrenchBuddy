from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import UserViewSet, PublicProfileView

router = DefaultRouter()
router.register(r'', UserViewSet, basename='user')

urlpatterns = router.urls + [
    path('profile/<str:username>/', PublicProfileView.as_view(), name='public-profile'),
]
