from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import VehicleViewSet, VehicleDocumentViewSet, VehiclePDFReportView

# Register 'documents' BEFORE '' so the specific prefix is matched
# before the vehicle detail pattern ^(?P<pk>[^/.]+)/$
router = DefaultRouter()
router.register(r'documents', VehicleDocumentViewSet, basename='vehicle-document')
router.register(r'', VehicleViewSet, basename='vehicle')

urlpatterns = router.urls + [
    path('<int:vehicle_id>/report/', VehiclePDFReportView.as_view(), name='vehicle-report'),
]
