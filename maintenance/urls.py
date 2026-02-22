from rest_framework.routers import DefaultRouter

from .views import TaskCatalogViewSet, MaintenanceEventViewSet, EventAttachmentViewSet, AccessoryViewSet

router = DefaultRouter()
router.register(r'catalog', TaskCatalogViewSet, basename='task-catalog')
router.register(r'events', MaintenanceEventViewSet, basename='maintenance-event')
router.register(r'attachments', EventAttachmentViewSet, basename='event-attachment')
router.register(r'accessories', AccessoryViewSet, basename='accessory')

urlpatterns = router.urls
