from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from .models import Vehicle
from .pdf_report import generate_vehicle_pdf
from .serializers import VehicleSerializer, VehicleListSerializer


class VehicleViewSet(viewsets.ModelViewSet):
    serializer_class = VehicleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Vehicle.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == 'list':
            return VehicleListSerializer
        return VehicleSerializer


class VehiclePDFReportView(APIView):
    """GET /api/vehicles/<id>/report/ — returns a PDF summary of the vehicle."""
    permission_classes = [IsAuthenticated]

    def get(self, request, vehicle_id):
        try:
            vehicle = Vehicle.objects.get(id=vehicle_id, user=request.user)
        except Vehicle.DoesNotExist:
            return HttpResponse(status=404)

        events = vehicle.maintenance_events.order_by('-date', '-created_at')
        accessories = vehicle.accessories.order_by('-created_at')

        pdf_bytes = generate_vehicle_pdf(vehicle, events, accessories)

        filename = f"wrenchbuddy_{vehicle.brand}_{vehicle.model}_{vehicle.year}.pdf"
        filename = filename.replace(' ', '_')

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
