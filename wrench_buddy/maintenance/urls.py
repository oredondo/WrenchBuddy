from rest_framework.routers import DefaultRouter

from .views import TaskCatalogViewSet, MaintenanceEventViewSet, MaintenanceTaskViewSet

router = DefaultRouter()
router.register(r'catalog', TaskCatalogViewSet, basename='task-catalog')
router.register(r'events', MaintenanceEventViewSet, basename='maintenance-event')
router.register(r'tasks', MaintenanceTaskViewSet, basename='maintenance-task')

urlpatterns = router.urls
