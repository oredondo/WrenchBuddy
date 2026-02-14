from rest_framework.routers import DefaultRouter

from .views import TaskCatalogViewSet, MaintenanceEventViewSet, MaintenanceTaskViewSet, EventAttachmentViewSet

router = DefaultRouter()
router.register(r'catalog', TaskCatalogViewSet, basename='task-catalog')
router.register(r'events', MaintenanceEventViewSet, basename='maintenance-event')
router.register(r'tasks', MaintenanceTaskViewSet, basename='maintenance-task')
router.register(r'attachments', EventAttachmentViewSet, basename='event-attachment')

urlpatterns = router.urls
