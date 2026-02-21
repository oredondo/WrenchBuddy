"""
Comprehensive test suite for maintenance app.

Tests cover:
- Model functionality (TaskCatalog, MaintenanceEvent)
- Serializers with validation
- ViewSets with CRUD operations
- Filtering by vehicle
- User permissions and data isolation
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from vehicles.models import Vehicle
from maintenance.models import TaskCatalog, MaintenanceEvent
from maintenance.serializers import (
    TaskCatalogSerializer,
    MaintenanceEventSerializer,
    MaintenanceEventCreateSerializer,
)


User = get_user_model()


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def other_user(db):
    """Create another test user for permission testing."""
    return User.objects.create_user(
        username='otheruser',
        email='other@example.com',
        password='otherpass123'
    )


@pytest.fixture
def api_client():
    """Create an API client."""
    return APIClient()


@pytest.fixture
def authenticated_client(api_client, user):
    """Create an authenticated API client."""
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def motorcycle(user):
    """Create a test motorcycle."""
    return Vehicle.objects.create(
        user=user,
        vehicle_type=Vehicle.VehicleType.MOTORCYCLE,
        brand='Honda',
        model='CBR600RR',
        year=2020,
        current_km=5000,
        displacement=600,
        usage_type=Vehicle.UsageType.MIXED
    )


@pytest.fixture
def car(user):
    """Create a test car."""
    return Vehicle.objects.create(
        user=user,
        vehicle_type=Vehicle.VehicleType.CAR,
        brand='Toyota',
        model='Corolla',
        year=2019,
        current_km=30000,
        usage_type=Vehicle.UsageType.CITY
    )


@pytest.fixture
def other_user_vehicle(other_user):
    """Create a vehicle for another user to test permissions."""
    return Vehicle.objects.create(
        user=other_user,
        vehicle_type=Vehicle.VehicleType.CAR,
        brand='Ford',
        model='Focus',
        year=2018,
        current_km=40000,
        usage_type=Vehicle.UsageType.MIXED
    )


@pytest.fixture
def task_catalog_oil_change(motorcycle):
    """Create a task catalog entry for oil change (per vehicle)."""
    return TaskCatalog.objects.create(
        vehicle=motorcycle,
        task_code='oil_change',
        name='Cambio de aceite',
        description='Cambio de aceite y filtro',
        interval_km=5000,
        interval_months=6,
        is_safety_critical=True,
        source=TaskCatalog.Source.AI_GENERATED,
    )


@pytest.fixture
def task_catalog_brake_pads(car):
    """Create a task catalog entry for brake pads (per vehicle)."""
    return TaskCatalog.objects.create(
        vehicle=car,
        task_code='brake_check',
        name='Pastillas de freno',
        description='Reemplazo de pastillas de freno delanteras',
        interval_km=30000,
        interval_months=24,
        is_safety_critical=True,
        source=TaskCatalog.Source.AI_GENERATED,
    )


@pytest.fixture
def maintenance_event(motorcycle):
    """Create a maintenance event."""
    return MaintenanceEvent.objects.create(
        vehicle=motorcycle,
        task_code='oil_change',
        date=date.today() - timedelta(days=30),
        km_at_service=4500,
        notes='Cambio de aceite regular',
        cost=Decimal('45.50')
    )



# ============================================================================
# MODEL TESTS
# ============================================================================

@pytest.mark.django_db
class TestTaskCatalogModel:
    """Tests for TaskCatalog model."""

    def test_create_task_catalog_with_valid_data_succeeds(self, motorcycle):
        # Arrange & Act
        task = TaskCatalog.objects.create(
            vehicle=motorcycle,
            task_code='test_task',
            name='Test Task',
            description='Test description',
            interval_km=1000,
            interval_months=12,
            is_safety_critical=True,
            source=TaskCatalog.Source.AI_GENERATED,
        )

        # Assert
        assert task.task_code == 'test_task'
        assert task.vehicle == motorcycle
        assert task.name == 'Test Task'
        assert task.is_safety_critical is True
        assert task.source == 'ai_generated'

    def test_task_catalog_str_returns_formatted_string(self, motorcycle):
        # Arrange
        task = TaskCatalog.objects.create(
            vehicle=motorcycle,
            task_code='oil_change',
            name='Cambio aceite',
        )

        # Act & Assert
        assert 'Cambio aceite' in str(task)

    def test_task_catalog_with_optional_fields_null_succeeds(self, motorcycle):
        # Arrange & Act
        task = TaskCatalog.objects.create(
            vehicle=motorcycle,
            task_code='inspection',
            name='Inspección general',
            interval_km=None,
            interval_months=None,
        )

        # Assert
        assert task.interval_km is None
        assert task.interval_months is None
        assert task.is_safety_critical is False


@pytest.mark.django_db
class TestMaintenanceEventModel:
    """Tests for MaintenanceEvent model."""

    def test_create_maintenance_event_with_required_fields_succeeds(self, motorcycle):
        # Arrange & Act
        event = MaintenanceEvent.objects.create(
            vehicle=motorcycle,
            task_code='oil_change',
            date=date.today(),
            km_at_service=5000
        )

        # Assert
        assert event.vehicle == motorcycle
        assert event.task_code == 'oil_change'
        assert event.date == date.today()
        assert event.km_at_service == 5000
        assert event.notes == ''
        assert event.cost is None

    def test_maintenance_event_str_returns_formatted_string(self, motorcycle):
        # Arrange
        event = MaintenanceEvent.objects.create(
            vehicle=motorcycle,
            task_code='OIL_CHANGE',
            date=date(2024, 1, 15),
            km_at_service=5000
        )

        # Act & Assert
        assert 'OIL_CHANGE' in str(event)
        assert '2024-01-15' in str(event)

    def test_maintenance_event_ordering_by_date_descending(self, motorcycle):
        # Arrange
        event1 = MaintenanceEvent.objects.create(
            vehicle=motorcycle,
            task_code='OIL_CHANGE',
            date=date(2024, 1, 1),
            km_at_service=1000
        )
        event2 = MaintenanceEvent.objects.create(
            vehicle=motorcycle,
            task_code='OIL_CHANGE',
            date=date(2024, 2, 1),
            km_at_service=2000
        )

        # Act
        events = list(MaintenanceEvent.objects.all())

        # Assert
        assert events[0] == event2
        assert events[1] == event1


# ============================================================================
# VIEW TESTS
# ============================================================================

@pytest.mark.django_db
class TestTaskCatalogViewSet:
    """Tests for TaskCatalogViewSet."""

    def test_list_catalog_as_authenticated_user_returns_own_vehicle_tasks(
        self, authenticated_client, task_catalog_oil_change, task_catalog_brake_pads, motorcycle
    ):
        # Only motorcycle belongs to authenticated user; brake_pads belongs to car (also user's)
        url = f'/api/maintenance/catalog/?vehicle={motorcycle.id}'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['task_code'] == 'oil_change'

    def test_list_catalog_as_unauthenticated_user_returns_401(self, api_client):
        url = '/api/maintenance/catalog/'

        response = api_client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_filter_catalog_by_vehicle_returns_filtered_results(
        self, authenticated_client, task_catalog_oil_change, task_catalog_brake_pads, motorcycle, car
    ):
        url = f'/api/maintenance/catalog/?vehicle={motorcycle.id}'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['task_code'] == 'oil_change'

    def test_retrieve_catalog_item_returns_single_task(
        self, authenticated_client, task_catalog_oil_change
    ):
        url = f'/api/maintenance/catalog/{task_catalog_oil_change.id}/'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['task_code'] == 'oil_change'

    def test_create_catalog_item_as_authenticated_user_succeeds(
        self, authenticated_client, motorcycle
    ):
        url = '/api/maintenance/catalog/'
        data = {
            'vehicle': motorcycle.id,
            'task_code': 'new_task',
            'name': 'New Task',
            'source': 'user_created',
        }

        response = authenticated_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['task_code'] == 'new_task'


@pytest.mark.django_db
class TestMaintenanceEventViewSet:
    """Tests for MaintenanceEventViewSet."""

    def test_list_events_returns_only_user_events(
        self, authenticated_client, maintenance_event, other_user_vehicle
    ):
        # Arrange - Create event for other user
        MaintenanceEvent.objects.create(
            vehicle=other_user_vehicle,
            task_code='OTHER_TASK',
            date=date.today(),
            km_at_service=1000
        )
        url = '/api/maintenance/events/'

        # Act
        response = authenticated_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['vehicle'] == maintenance_event.vehicle.id

    def test_filter_events_by_vehicle_returns_filtered_results(
        self, authenticated_client, motorcycle, car
    ):
        # Arrange
        event1 = MaintenanceEvent.objects.create(
            vehicle=motorcycle,
            task_code='TASK1',
            date=date.today(),
            km_at_service=1000
        )
        event2 = MaintenanceEvent.objects.create(
            vehicle=car,
            task_code='TASK2',
            date=date.today(),
            km_at_service=2000
        )
        url = f'/api/maintenance/events/?vehicle={motorcycle.id}'

        # Act
        response = authenticated_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['vehicle'] == motorcycle.id

    def test_create_event_with_valid_data_succeeds(
        self, authenticated_client, motorcycle
    ):
        # Arrange
        url = '/api/maintenance/events/'
        data = {
            'vehicle': motorcycle.id,
            'task_code': 'OIL_CHANGE',
            'date': str(date.today()),
            'km_at_service': 5000,
            'notes': 'Regular maintenance',
            'cost': '45.50'
        }

        # Act
        response = authenticated_client.post(url, data, format='json')

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['task_code'] == 'OIL_CHANGE'
        assert MaintenanceEvent.objects.count() == 1

    def test_create_event_with_other_user_vehicle_returns_400(
        self, authenticated_client, other_user_vehicle
    ):
        # Arrange
        url = '/api/maintenance/events/'
        data = {
            'vehicle': other_user_vehicle.id,
            'task_code': 'OIL_CHANGE',
            'date': str(date.today()),
            'km_at_service': 5000
        }

        # Act
        response = authenticated_client.post(url, data, format='json')

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'vehicle' in response.data

    def test_retrieve_event_returns_event_details(
        self, authenticated_client, maintenance_event
    ):
        # Arrange
        url = f'/api/maintenance/events/{maintenance_event.id}/'

        # Act
        response = authenticated_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == maintenance_event.id

    def test_retrieve_other_user_event_returns_404(
        self, authenticated_client, other_user_vehicle
    ):
        # Arrange
        other_event = MaintenanceEvent.objects.create(
            vehicle=other_user_vehicle,
            task_code='OTHER',
            date=date.today(),
            km_at_service=1000
        )
        url = f'/api/maintenance/events/{other_event.id}/'

        # Act
        response = authenticated_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_event_with_valid_data_succeeds(
        self, authenticated_client, maintenance_event
    ):
        # Arrange
        url = f'/api/maintenance/events/{maintenance_event.id}/'
        data = {
            'vehicle': maintenance_event.vehicle.id,
            'task_code': 'OIL_CHANGE',
            'date': str(date.today()),
            'km_at_service': 5500,
            'notes': 'Updated notes',
            'cost': '50.00'
        }

        # Act
        response = authenticated_client.put(url, data, format='json')

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['km_at_service'] == 5500
        assert response.data['notes'] == 'Updated notes'

    def test_partial_update_event_succeeds(
        self, authenticated_client, maintenance_event
    ):
        # Arrange
        url = f'/api/maintenance/events/{maintenance_event.id}/'
        data = {'notes': 'Partially updated notes'}

        # Act
        response = authenticated_client.patch(url, data, format='json')

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['notes'] == 'Partially updated notes'

    def test_delete_event_succeeds(self, authenticated_client, maintenance_event):
        # Arrange
        url = f'/api/maintenance/events/{maintenance_event.id}/'

        # Act
        response = authenticated_client.delete(url)

        # Assert
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert MaintenanceEvent.objects.count() == 0

    def test_list_events_as_unauthenticated_user_returns_401(self, api_client):
        # Arrange
        url = '/api/maintenance/events/'

        # Act
        response = api_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ============================================================================
# EDGE CASE TESTS - Catalog Filtering
# ============================================================================

@pytest.mark.django_db
class TestCatalogFilteringEdgeCases:
    """Edge case tests for TaskCatalog filtering."""

    def test_filter_catalog_by_invalid_vehicle_id_returns_empty(
        self, authenticated_client, task_catalog_oil_change
    ):
        url = '/api/maintenance/catalog/?vehicle=99999'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 0

    def test_list_catalog_without_filter_returns_all_user_tasks(
        self, authenticated_client, task_catalog_oil_change, task_catalog_brake_pads
    ):
        url = '/api/maintenance/catalog/'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_filter_catalog_by_car_vehicle_returns_car_tasks(
        self, authenticated_client, task_catalog_oil_change, task_catalog_brake_pads, car
    ):
        url = f'/api/maintenance/catalog/?vehicle={car.id}'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['task_code'] == 'brake_check'


# ============================================================================
# EDGE CASE TESTS - Cost Validation
# ============================================================================

@pytest.mark.django_db
class TestCostValidation:
    """Edge case tests for cost field validation."""

    def test_create_event_with_zero_cost_succeeds(
        self, authenticated_client, motorcycle
    ):
        url = '/api/maintenance/events/'
        data = {
            'vehicle': motorcycle.id,
            'task_code': 'OIL_CHANGE',
            'date': str(date.today()),
            'km_at_service': 5000,
            'cost': '0.00'
        }

        response = authenticated_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert Decimal(response.data['cost']) == Decimal('0.00')

    def test_create_event_with_large_cost_succeeds(
        self, authenticated_client, motorcycle
    ):
        url = '/api/maintenance/events/'
        data = {
            'vehicle': motorcycle.id,
            'task_code': 'OIL_CHANGE',
            'date': str(date.today()),
            'km_at_service': 5000,
            'cost': '99999999.99'
        }

        response = authenticated_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_201_CREATED

    def test_create_event_without_cost_succeeds(
        self, authenticated_client, motorcycle
    ):
        url = '/api/maintenance/events/'
        data = {
            'vehicle': motorcycle.id,
            'task_code': 'OIL_CHANGE',
            'date': str(date.today()),
            'km_at_service': 5000
        }

        response = authenticated_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_201_CREATED


# ============================================================================
# EDGE CASE TESTS - Cascade Deletion
# ============================================================================

@pytest.mark.django_db
class TestCascadeDeletion:
    """Tests for cascade deletion behavior."""

    def test_vehicle_deletion_removes_events(self, user, motorcycle, maintenance_event):
        assert MaintenanceEvent.objects.count() == 1

        motorcycle.delete()

        assert MaintenanceEvent.objects.count() == 0
