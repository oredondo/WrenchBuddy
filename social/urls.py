from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    GaragePhotoViewSet,
    VehicleCommentViewSet,
    GaragePhotoCommentViewSet,
    FollowView,
    FollowersView,
    FollowingView,
    FeedView,
    VehicleLikeView,
    GaragePhotoLikeView,
)

router = DefaultRouter()
router.register(r'photos', GaragePhotoViewSet, basename='garage-photo')
router.register(r'vehicle-comments', VehicleCommentViewSet, basename='vehicle-comment')
router.register(r'photo-comments', GaragePhotoCommentViewSet, basename='photo-comment')

urlpatterns = router.urls + [
    path('follow/<str:username>/',   FollowView.as_view(),    name='social-follow'),
    path('followers/<str:username>/', FollowersView.as_view(), name='social-followers'),
    path('following/<str:username>/', FollowingView.as_view(), name='social-following'),
    path('feed/',                    FeedView.as_view(),       name='social-feed'),
    path('vehicles/<int:pk>/like/',  VehicleLikeView.as_view(),     name='vehicle-like'),
    path('photos/<int:pk>/like/',    GaragePhotoLikeView.as_view(), name='photo-like'),
]
