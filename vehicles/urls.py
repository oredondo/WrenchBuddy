from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import VehicleViewSet, VehiclePDFReportView

router = DefaultRouter()
router.register(r'', VehicleViewSet, basename='vehicle')

urlpatterns = router.urls + [
    path('<int:vehicle_id>/report/', VehiclePDFReportView.as_view(), name='vehicle-report'),
]
