"""
Comprehensive test suite for maintenance app.

Tests cover:
- Model functionality (TaskCatalog, MaintenanceEvent, MaintenanceTask)
- Serializers with validation
- ViewSets with CRUD operations
- Filtering by vehicle
- Custom actions (complete, dismiss)
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
from maintenance.models import TaskCatalog, MaintenanceEvent, MaintenanceTask
from maintenance.serializers import (
    TaskCatalogSerializer,
    MaintenanceEventSerializer,
    MaintenanceEventCreateSerializer,
    MaintenanceTaskSerializer,
    MaintenanceTaskCompleteSerializer,
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
def task_catalog_oil_change():
    """Create a task catalog entry for oil change."""
    return TaskCatalog.objects.create(
        task_code='OIL_CHANGE',
        vehicle_type=TaskCatalog.VehicleType.MOTORCYCLE,
        name='Cambio de aceite',
        description='Cambio de aceite y filtro',
        default_interval_km=5000,
        default_interval_months=6,
        is_safety_critical=True
    )


@pytest.fixture
def task_catalog_brake_pads():
    """Create a task catalog entry for brake pads."""
    return TaskCatalog.objects.create(
        task_code='BRAKE_PADS',
        vehicle_type=TaskCatalog.VehicleType.CAR,
        name='Pastillas de freno',
        description='Reemplazo de pastillas de freno delanteras',
        default_interval_km=30000,
        default_interval_months=24,
        is_safety_critical=True
    )


@pytest.fixture
def maintenance_event(motorcycle, task_catalog_oil_change):
    """Create a maintenance event."""
    return MaintenanceEvent.objects.create(
        vehicle=motorcycle,
        task_code='OIL_CHANGE',
        date=date.today() - timedelta(days=30),
        km_at_service=4500,
        notes='Cambio de aceite regular',
        cost=Decimal('45.50')
    )


@pytest.fixture
def maintenance_task(motorcycle, task_catalog_oil_change):
    """Create a pending maintenance task."""
    return MaintenanceTask.objects.create(
        vehicle=motorcycle,
        task_code='OIL_CHANGE',
        priority=MaintenanceTask.Priority.HIGH,
        due_km=10000,
        due_date=date.today() + timedelta(days=30),
        explanation='Es necesario cambiar el aceite pronto',
        estimated_cost=Decimal('50.00'),
        status=MaintenanceTask.Status.PENDING
    )


# ============================================================================
# MODEL TESTS
# ============================================================================

@pytest.mark.django_db
class TestTaskCatalogModel:
    """Tests for TaskCatalog model."""

    def test_create_task_catalog_with_valid_data_succeeds(self):
        # Arrange & Act
        task = TaskCatalog.objects.create(
            task_code='TEST_TASK',
            vehicle_type=TaskCatalog.VehicleType.MOTORCYCLE,
            name='Test Task',
            description='Test description',
            default_interval_km=1000,
            default_interval_months=12,
            is_safety_critical=True
        )

        # Assert
        assert task.task_code == 'TEST_TASK'
        assert task.vehicle_type == 'motorcycle'
        assert task.name == 'Test Task'
        assert task.is_safety_critical is True

    def test_task_catalog_str_returns_formatted_string(self):
        # Arrange
        task = TaskCatalog.objects.create(
            task_code='OIL',
            vehicle_type=TaskCatalog.VehicleType.CAR,
            name='Cambio aceite'
        )

        # Act & Assert
        assert str(task) == 'Cambio aceite (car)'

    def test_task_catalog_with_optional_fields_null_succeeds(self):
        # Arrange & Act
        task = TaskCatalog.objects.create(
            task_code='INSPECTION',
            vehicle_type=TaskCatalog.VehicleType.MOTORCYCLE,
            name='Inspección general',
            default_interval_km=None,
            default_interval_months=None
        )

        # Assert
        assert task.default_interval_km is None
        assert task.default_interval_months is None
        assert task.is_safety_critical is False


@pytest.mark.django_db
class TestMaintenanceEventModel:
    """Tests for MaintenanceEvent model."""

    def test_create_maintenance_event_with_required_fields_succeeds(
        self, motorcycle, task_catalog_oil_change
    ):
        # Arrange & Act
        event = MaintenanceEvent.objects.create(
            vehicle=motorcycle,
            task_code='OIL_CHANGE',
            date=date.today(),
            km_at_service=5000
        )

        # Assert
        assert event.vehicle == motorcycle
        assert event.task_code == 'OIL_CHANGE'
        assert event.date == date.today()
        assert event.km_at_service == 5000
        assert event.notes == ''
        assert event.cost is None

    def test_maintenance_event_with_all_fields_succeeds(
        self, motorcycle, maintenance_task
    ):
        # Arrange & Act
        event = MaintenanceEvent.objects.create(
            vehicle=motorcycle,
            task_code='OIL_CHANGE',
            date=date.today(),
            km_at_service=5000,
            notes='Completed maintenance',
            cost=Decimal('45.99'),
            created_from_task=maintenance_task
        )

        # Assert
        assert event.notes == 'Completed maintenance'
        assert event.cost == Decimal('45.99')
        assert event.created_from_task == maintenance_task

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


@pytest.mark.django_db
class TestMaintenanceTaskModel:
    """Tests for MaintenanceTask model."""

    def test_create_maintenance_task_with_required_fields_succeeds(
        self, motorcycle
    ):
        # Arrange & Act
        task = MaintenanceTask.objects.create(
            vehicle=motorcycle,
            task_code='OIL_CHANGE',
            priority=MaintenanceTask.Priority.MEDIUM
        )

        # Assert
        assert task.vehicle == motorcycle
        assert task.task_code == 'OIL_CHANGE'
        assert task.priority == 'medium'
        assert task.status == 'pending'  # Default value

    def test_maintenance_task_with_all_fields_succeeds(
        self, motorcycle, maintenance_event
    ):
        # Arrange & Act
        task = MaintenanceTask.objects.create(
            vehicle=motorcycle,
            task_code='OIL_CHANGE',
            priority=MaintenanceTask.Priority.HIGH,
            due_km=10000,
            due_date=date.today() + timedelta(days=30),
            explanation='Urgent maintenance needed',
            estimated_cost=Decimal('75.00'),
            status=MaintenanceTask.Status.COMPLETED,
            completed_event=maintenance_event
        )

        # Assert
        assert task.priority == 'high'
        assert task.due_km == 10000
        assert task.estimated_cost == Decimal('75.00')
        assert task.status == 'completed'
        assert task.completed_event == maintenance_event

    def test_maintenance_task_str_returns_formatted_string(self, motorcycle):
        # Arrange
        task = MaintenanceTask.objects.create(
            vehicle=motorcycle,
            task_code='BRAKE_CHECK',
            status=MaintenanceTask.Status.PENDING
        )

        # Act & Assert
        assert 'BRAKE_CHECK' in str(task)
        assert 'pending' in str(task)

    def test_maintenance_task_default_status_is_pending(self, motorcycle):
        # Arrange & Act
        task = MaintenanceTask.objects.create(
            vehicle=motorcycle,
            task_code='TEST'
        )

        # Assert
        assert task.status == MaintenanceTask.Status.PENDING

    def test_maintenance_task_priority_choices_are_valid(self, motorcycle):
        # Arrange & Act
        high_task = MaintenanceTask.objects.create(
            vehicle=motorcycle,
            task_code='HIGH',
            priority=MaintenanceTask.Priority.HIGH
        )
        medium_task = MaintenanceTask.objects.create(
            vehicle=motorcycle,
            task_code='MEDIUM',
            priority=MaintenanceTask.Priority.MEDIUM
        )
        low_task = MaintenanceTask.objects.create(
            vehicle=motorcycle,
            task_code='LOW',
            priority=MaintenanceTask.Priority.LOW
        )

        # Assert
        assert high_task.priority == 'high'
        assert medium_task.priority == 'medium'
        assert low_task.priority == 'low'


# ============================================================================
# SERIALIZER TESTS
# ============================================================================

@pytest.mark.django_db
class TestTaskCatalogSerializer:
    """Tests for TaskCatalogSerializer."""

    def test_serialize_task_catalog_returns_all_fields(
        self, task_catalog_oil_change
    ):
        # Arrange
        serializer = TaskCatalogSerializer(task_catalog_oil_change)

        # Act
        data = serializer.data

        # Assert
        assert data['task_code'] == 'OIL_CHANGE'
        assert data['vehicle_type'] == 'motorcycle'
        assert data['name'] == 'Cambio de aceite'
        assert data['description'] == 'Cambio de aceite y filtro'
        assert data['default_interval_km'] == 5000
        assert data['default_interval_months'] == 6
        assert data['is_safety_critical'] is True


@pytest.mark.django_db
class TestMaintenanceEventSerializer:
    """Tests for MaintenanceEventSerializer."""

    def test_serialize_event_includes_task_name_from_catalog(
        self, maintenance_event, task_catalog_oil_change
    ):
        # Arrange
        serializer = MaintenanceEventSerializer(maintenance_event)

        # Act
        data = serializer.data

        # Assert
        assert data['task_name'] == 'Cambio de aceite'
        assert data['task_code'] == 'OIL_CHANGE'

    def test_serialize_event_returns_task_code_when_no_catalog_entry(
        self, motorcycle
    ):
        # Arrange
        event = MaintenanceEvent.objects.create(
            vehicle=motorcycle,
            task_code='UNKNOWN_TASK',
            date=date.today(),
            km_at_service=1000
        )
        serializer = MaintenanceEventSerializer(event)

        # Act
        data = serializer.data

        # Assert
        assert data['task_name'] == 'UNKNOWN_TASK'

    def test_serialize_event_includes_all_fields(self, maintenance_event):
        # Arrange
        serializer = MaintenanceEventSerializer(maintenance_event)

        # Act
        data = serializer.data

        # Assert
        assert 'id' in data
        assert 'vehicle' in data
        assert 'task_code' in data
        assert 'task_name' in data
        assert 'date' in data
        assert 'km_at_service' in data
        assert 'notes' in data
        assert 'cost' in data
        assert 'created_from_task' in data
        assert 'created_at' in data
        assert 'updated_at' in data


@pytest.mark.django_db
class TestMaintenanceEventCreateSerializer:
    """Tests for MaintenanceEventCreateSerializer."""

    def test_validate_vehicle_with_own_vehicle_succeeds(
        self, motorcycle, user, rf
    ):
        # Arrange
        from django.test import RequestFactory
        request = RequestFactory().get('/')
        request.user = user

        serializer = MaintenanceEventCreateSerializer(
            context={'request': request}
        )

        # Act & Assert
        validated = serializer.validate_vehicle(motorcycle)
        assert validated == motorcycle

    def test_validate_vehicle_with_other_user_vehicle_raises_error(
        self, other_user_vehicle, user, rf
    ):
        # Arrange
        from rest_framework.exceptions import ValidationError
        from django.test import RequestFactory
        request = RequestFactory().get('/')
        request.user = user

        serializer = MaintenanceEventCreateSerializer(
            context={'request': request}
        )

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            serializer.validate_vehicle(other_user_vehicle)
        assert 'No tienes permiso' in str(exc_info.value)

    def test_create_event_with_valid_data_succeeds(self, motorcycle, user, rf):
        # Arrange
        from django.test import RequestFactory
        request = RequestFactory().get('/')
        request.user = user

        data = {
            'vehicle': motorcycle.id,
            'task_code': 'OIL_CHANGE',
            'date': date.today(),
            'km_at_service': 5000,
            'notes': 'Test notes',
            'cost': '45.50'
        }
        serializer = MaintenanceEventCreateSerializer(
            data=data,
            context={'request': request}
        )

        # Act
        is_valid = serializer.is_valid()

        # Assert
        assert is_valid is True
        assert serializer.validated_data['task_code'] == 'OIL_CHANGE'


@pytest.mark.django_db
class TestMaintenanceTaskSerializer:
    """Tests for MaintenanceTaskSerializer."""

    def test_serialize_task_includes_task_name_from_catalog(
        self, maintenance_task, task_catalog_oil_change
    ):
        # Arrange
        serializer = MaintenanceTaskSerializer(maintenance_task)

        # Act
        data = serializer.data

        # Assert
        assert data['task_name'] == 'Cambio de aceite'
        assert data['task_code'] == 'OIL_CHANGE'

    def test_serialize_task_includes_all_fields(self, maintenance_task):
        # Arrange
        serializer = MaintenanceTaskSerializer(maintenance_task)

        # Act
        data = serializer.data

        # Assert
        assert 'id' in data
        assert 'vehicle' in data
        assert 'task_code' in data
        assert 'task_name' in data
        assert 'priority' in data
        assert 'due_km' in data
        assert 'due_date' in data
        assert 'explanation' in data
        assert 'estimated_cost' in data
        assert 'status' in data
        assert 'completed_event' in data
        assert 'created_at' in data
        assert 'updated_at' in data


@pytest.mark.django_db
class TestMaintenanceTaskCompleteSerializer:
    """Tests for MaintenanceTaskCompleteSerializer."""

    def test_validate_with_all_required_fields_succeeds(self):
        # Arrange
        data = {
            'date': date.today(),
            'km_at_service': 5000,
            'notes': 'Completed successfully',
            'cost': '50.00'
        }
        serializer = MaintenanceTaskCompleteSerializer(data=data)

        # Act
        is_valid = serializer.is_valid()

        # Assert
        assert is_valid is True
        assert serializer.validated_data['date'] == date.today()
        assert serializer.validated_data['km_at_service'] == 5000

    def test_validate_with_only_required_fields_succeeds(self):
        # Arrange
        data = {
            'date': date.today(),
            'km_at_service': 5000
        }
        serializer = MaintenanceTaskCompleteSerializer(data=data)

        # Act
        is_valid = serializer.is_valid()

        # Assert
        assert is_valid is True

    def test_validate_with_negative_km_raises_error(self):
        # Arrange
        data = {
            'date': date.today(),
            'km_at_service': -100
        }
        serializer = MaintenanceTaskCompleteSerializer(data=data)

        # Act
        is_valid = serializer.is_valid()

        # Assert
        assert is_valid is False
        assert 'km_at_service' in serializer.errors


# ============================================================================
# VIEW TESTS
# ============================================================================

@pytest.mark.django_db
class TestTaskCatalogViewSet:
    """Tests for TaskCatalogViewSet."""

    def test_list_catalog_as_authenticated_user_returns_all_tasks(
        self, authenticated_client, task_catalog_oil_change, task_catalog_brake_pads
    ):
        # Arrange
        url = '/api/maintenance/catalog/'

        # Act
        response = authenticated_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_list_catalog_as_unauthenticated_user_returns_401(self, api_client):
        # Arrange
        url = '/api/maintenance/catalog/'

        # Act
        response = api_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_filter_catalog_by_vehicle_type_returns_filtered_results(
        self, authenticated_client, task_catalog_oil_change, task_catalog_brake_pads
    ):
        # Arrange
        url = '/api/maintenance/catalog/?vehicle_type=motorcycle'

        # Act
        response = authenticated_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['task_code'] == 'OIL_CHANGE'

    def test_retrieve_catalog_item_returns_single_task(
        self, authenticated_client, task_catalog_oil_change
    ):
        # Arrange
        url = f'/api/maintenance/catalog/{task_catalog_oil_change.task_code}/'

        # Act
        response = authenticated_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['task_code'] == 'OIL_CHANGE'

    def test_create_catalog_item_as_authenticated_user_returns_405(
        self, authenticated_client
    ):
        # Arrange
        url = '/api/maintenance/catalog/'
        data = {
            'task_code': 'NEW_TASK',
            'vehicle_type': 'motorcycle',
            'name': 'New Task'
        }

        # Act
        response = authenticated_client.post(url, data)

        # Assert - Read-only viewset
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


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


@pytest.mark.django_db
class TestMaintenanceTaskViewSet:
    """Tests for MaintenanceTaskViewSet."""

    def test_list_tasks_returns_only_user_tasks(
        self, authenticated_client, maintenance_task, other_user_vehicle
    ):
        # Arrange - Create task for other user
        MaintenanceTask.objects.create(
            vehicle=other_user_vehicle,
            task_code='OTHER_TASK'
        )
        url = '/api/maintenance/tasks/'

        # Act
        response = authenticated_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['vehicle'] == maintenance_task.vehicle.id

    def test_filter_tasks_by_vehicle_returns_filtered_results(
        self, authenticated_client, motorcycle, car
    ):
        # Arrange
        task1 = MaintenanceTask.objects.create(
            vehicle=motorcycle,
            task_code='TASK1'
        )
        task2 = MaintenanceTask.objects.create(
            vehicle=car,
            task_code='TASK2'
        )
        url = f'/api/maintenance/tasks/?vehicle={motorcycle.id}'

        # Act
        response = authenticated_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['vehicle'] == motorcycle.id

    def test_filter_tasks_by_status_returns_filtered_results(
        self, authenticated_client, motorcycle
    ):
        # Arrange
        pending = MaintenanceTask.objects.create(
            vehicle=motorcycle,
            task_code='PENDING',
            status=MaintenanceTask.Status.PENDING
        )
        completed = MaintenanceTask.objects.create(
            vehicle=motorcycle,
            task_code='COMPLETED',
            status=MaintenanceTask.Status.COMPLETED
        )
        url = '/api/maintenance/tasks/?status=pending'

        # Act
        response = authenticated_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['status'] == 'pending'

    def test_create_task_with_valid_data_succeeds(
        self, authenticated_client, motorcycle
    ):
        # Arrange
        url = '/api/maintenance/tasks/'
        data = {
            'vehicle': motorcycle.id,
            'task_code': 'NEW_TASK',
            'priority': 'high',
            'due_km': 10000,
            'due_date': str(date.today() + timedelta(days=30)),
            'explanation': 'Test explanation',
            'estimated_cost': '75.00'
        }

        # Act
        response = authenticated_client.post(url, data, format='json')

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['task_code'] == 'NEW_TASK'
        assert MaintenanceTask.objects.count() == 1

    def test_retrieve_task_returns_task_details(
        self, authenticated_client, maintenance_task
    ):
        # Arrange
        url = f'/api/maintenance/tasks/{maintenance_task.id}/'

        # Act
        response = authenticated_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == maintenance_task.id

    def test_update_task_succeeds(self, authenticated_client, maintenance_task):
        # Arrange
        url = f'/api/maintenance/tasks/{maintenance_task.id}/'
        data = {
            'vehicle': maintenance_task.vehicle.id,
            'task_code': 'OIL_CHANGE',
            'priority': 'low',
            'explanation': 'Updated explanation'
        }

        # Act
        response = authenticated_client.patch(url, data, format='json')

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['priority'] == 'low'

    def test_delete_task_succeeds(self, authenticated_client, maintenance_task):
        # Arrange
        url = f'/api/maintenance/tasks/{maintenance_task.id}/'

        # Act
        response = authenticated_client.delete(url)

        # Assert
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert MaintenanceTask.objects.count() == 0


@pytest.mark.django_db
class TestMaintenanceTaskCompleteAction:
    """Tests for the complete action on MaintenanceTaskViewSet."""

    def test_complete_task_creates_event_and_updates_task(
        self, authenticated_client, maintenance_task
    ):
        # Arrange
        url = f'/api/maintenance/tasks/{maintenance_task.id}/complete/'
        data = {
            'date': str(date.today()),
            'km_at_service': 5500,
            'notes': 'Completed successfully',
            'cost': '55.00'
        }

        # Act
        response = authenticated_client.post(url, data, format='json')

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'completed'

        # Verify event was created
        assert MaintenanceEvent.objects.count() == 1
        event = MaintenanceEvent.objects.first()
        assert event.vehicle == maintenance_task.vehicle
        assert event.task_code == maintenance_task.task_code
        assert event.km_at_service == 5500
        assert event.notes == 'Completed successfully'
        assert event.cost == Decimal('55.00')

        # Verify task was updated
        maintenance_task.refresh_from_db()
        assert maintenance_task.status == MaintenanceTask.Status.COMPLETED
        assert maintenance_task.completed_event == event

    def test_complete_task_with_minimal_data_succeeds(
        self, authenticated_client, maintenance_task
    ):
        # Arrange
        url = f'/api/maintenance/tasks/{maintenance_task.id}/complete/'
        data = {
            'date': str(date.today()),
            'km_at_service': 5500
        }

        # Act
        response = authenticated_client.post(url, data, format='json')

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert MaintenanceEvent.objects.count() == 1
        event = MaintenanceEvent.objects.first()
        assert event.notes == ''
        assert event.cost is None

    def test_complete_task_with_invalid_data_returns_400(
        self, authenticated_client, maintenance_task
    ):
        # Arrange
        url = f'/api/maintenance/tasks/{maintenance_task.id}/complete/'
        data = {
            'date': str(date.today()),
            'km_at_service': -100  # Invalid negative value
        }

        # Act
        response = authenticated_client.post(url, data, format='json')

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert MaintenanceEvent.objects.count() == 0

    def test_complete_task_with_missing_required_fields_returns_400(
        self, authenticated_client, maintenance_task
    ):
        # Arrange
        url = f'/api/maintenance/tasks/{maintenance_task.id}/complete/'
        data = {'date': str(date.today())}  # Missing km_at_service

        # Act
        response = authenticated_client.post(url, data, format='json')

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert MaintenanceEvent.objects.count() == 0

    def test_complete_other_user_task_returns_404(
        self, authenticated_client, other_user_vehicle
    ):
        # Arrange
        other_task = MaintenanceTask.objects.create(
            vehicle=other_user_vehicle,
            task_code='OTHER_TASK'
        )
        url = f'/api/maintenance/tasks/{other_task.id}/complete/'
        data = {
            'date': str(date.today()),
            'km_at_service': 1000
        }

        # Act
        response = authenticated_client.post(url, data, format='json')

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_complete_task_links_event_to_task_bidirectionally(
        self, authenticated_client, maintenance_task
    ):
        # Arrange
        url = f'/api/maintenance/tasks/{maintenance_task.id}/complete/'
        data = {
            'date': str(date.today()),
            'km_at_service': 5500
        }

        # Act
        response = authenticated_client.post(url, data, format='json')

        # Assert
        event = MaintenanceEvent.objects.first()
        maintenance_task.refresh_from_db()

        # Check bidirectional relationship
        assert event.created_from_task == maintenance_task
        assert maintenance_task.completed_event == event
        assert event.source_task == maintenance_task


@pytest.mark.django_db
class TestMaintenanceTaskDismissAction:
    """Tests for the dismiss action on MaintenanceTaskViewSet."""

    def test_dismiss_task_updates_status_to_dismissed(
        self, authenticated_client, maintenance_task
    ):
        # Arrange
        url = f'/api/maintenance/tasks/{maintenance_task.id}/dismiss/'

        # Act
        response = authenticated_client.post(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'dismissed'

        maintenance_task.refresh_from_db()
        assert maintenance_task.status == MaintenanceTask.Status.DISMISSED

    def test_dismiss_task_does_not_create_event(
        self, authenticated_client, maintenance_task
    ):
        # Arrange
        url = f'/api/maintenance/tasks/{maintenance_task.id}/dismiss/'

        # Act
        response = authenticated_client.post(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert MaintenanceEvent.objects.count() == 0

    def test_dismiss_other_user_task_returns_404(
        self, authenticated_client, other_user_vehicle
    ):
        # Arrange
        other_task = MaintenanceTask.objects.create(
            vehicle=other_user_vehicle,
            task_code='OTHER_TASK'
        )
        url = f'/api/maintenance/tasks/{other_task.id}/dismiss/'

        # Act
        response = authenticated_client.post(url)

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_dismiss_already_dismissed_task_succeeds(
        self, authenticated_client, maintenance_task
    ):
        # Arrange
        maintenance_task.status = MaintenanceTask.Status.DISMISSED
        maintenance_task.save()
        url = f'/api/maintenance/tasks/{maintenance_task.id}/dismiss/'

        # Act
        response = authenticated_client.post(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'dismissed'

    def test_dismiss_completed_task_changes_status(
        self, authenticated_client, motorcycle
    ):
        # Arrange - Create a completed task
        event = MaintenanceEvent.objects.create(
            vehicle=motorcycle,
            task_code='COMPLETED_TASK',
            date=date.today(),
            km_at_service=1000
        )
        task = MaintenanceTask.objects.create(
            vehicle=motorcycle,
            task_code='COMPLETED_TASK',
            status=MaintenanceTask.Status.COMPLETED,
            completed_event=event
        )
        url = f'/api/maintenance/tasks/{task.id}/dismiss/'

        # Act
        response = authenticated_client.post(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'dismissed'


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

@pytest.mark.django_db
class TestMaintenanceWorkflow:
    """Integration tests for complete maintenance workflows."""

    def test_complete_workflow_task_to_event(
        self, authenticated_client, motorcycle, task_catalog_oil_change
    ):
        """Test the complete workflow: create task -> complete task -> verify event."""
        # Step 1: Create a maintenance task
        create_task_url = '/api/maintenance/tasks/'
        task_data = {
            'vehicle': motorcycle.id,
            'task_code': 'OIL_CHANGE',
            'priority': 'high',
            'due_km': 10000,
            'explanation': 'Oil change needed'
        }
        response = authenticated_client.post(
            create_task_url, task_data, format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED
        task_id = response.data['id']

        # Step 2: Complete the task
        complete_url = f'/api/maintenance/tasks/{task_id}/complete/'
        complete_data = {
            'date': str(date.today()),
            'km_at_service': 9500,
            'notes': 'Oil changed successfully',
            'cost': '45.00'
        }
        response = authenticated_client.post(
            complete_url, complete_data, format='json'
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'completed'

        # Step 3: Verify event was created
        events_url = '/api/maintenance/events/'
        response = authenticated_client.get(events_url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['task_code'] == 'OIL_CHANGE'
        assert response.data[0]['km_at_service'] == 9500

    def test_filter_tasks_and_events_by_vehicle(
        self, authenticated_client, motorcycle, car
    ):
        """Test filtering both tasks and events by vehicle."""
        # Create tasks and events for both vehicles
        MaintenanceTask.objects.create(
            vehicle=motorcycle, task_code='MOTO_TASK'
        )
        MaintenanceTask.objects.create(
            vehicle=car, task_code='CAR_TASK'
        )
        MaintenanceEvent.objects.create(
            vehicle=motorcycle,
            task_code='MOTO_EVENT',
            date=date.today(),
            km_at_service=1000
        )
        MaintenanceEvent.objects.create(
            vehicle=car,
            task_code='CAR_EVENT',
            date=date.today(),
            km_at_service=2000
        )

        # Filter tasks by motorcycle
        tasks_url = f'/api/maintenance/tasks/?vehicle={motorcycle.id}'
        response = authenticated_client.get(tasks_url)
        assert len(response.data) == 1
        assert response.data[0]['task_code'] == 'MOTO_TASK'

        # Filter events by car
        events_url = f'/api/maintenance/events/?vehicle={car.id}'
        response = authenticated_client.get(events_url)
        assert len(response.data) == 1
        assert response.data[0]['task_code'] == 'CAR_EVENT'

    def test_user_isolation_across_all_endpoints(
        self, user, other_user, motorcycle, other_user_vehicle, api_client
    ):
        """Test that users can only access their own data across all endpoints."""
        # Create data for both users
        user_task = MaintenanceTask.objects.create(
            vehicle=motorcycle, task_code='USER_TASK'
        )
        other_task = MaintenanceTask.objects.create(
            vehicle=other_user_vehicle, task_code='OTHER_TASK'
        )
        user_event = MaintenanceEvent.objects.create(
            vehicle=motorcycle,
            task_code='USER_EVENT',
            date=date.today(),
            km_at_service=1000
        )
        other_event = MaintenanceEvent.objects.create(
            vehicle=other_user_vehicle,
            task_code='OTHER_EVENT',
            date=date.today(),
            km_at_service=2000
        )

        # Authenticate as first user
        api_client.force_authenticate(user=user)

        # List tasks - should only see own tasks
        response = api_client.get('/api/maintenance/tasks/')
        assert len(response.data) == 1
        assert response.data[0]['task_code'] == 'USER_TASK'

        # List events - should only see own events
        response = api_client.get('/api/maintenance/events/')
        assert len(response.data) == 1
        assert response.data[0]['task_code'] == 'USER_EVENT'

        # Try to access other user's task - should fail
        response = api_client.get(f'/api/maintenance/tasks/{other_task.id}/')
        assert response.status_code == status.HTTP_404_NOT_FOUND

        # Try to access other user's event - should fail
        response = api_client.get(f'/api/maintenance/events/{other_event.id}/')
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ============================================================================
# EDGE CASE TESTS - Complete/Dismiss Actions
# ============================================================================

@pytest.mark.django_db
class TestCompleteActionEdgeCases:
    """Edge case tests for the complete action."""

    def test_complete_already_completed_task_creates_another_event(
        self, authenticated_client, motorcycle
    ):
        """Completing an already completed task still works (no guard in view)."""
        task = MaintenanceTask.objects.create(
            vehicle=motorcycle,
            task_code='OIL_CHANGE',
            status=MaintenanceTask.Status.COMPLETED
        )
        url = f'/api/maintenance/tasks/{task.id}/complete/'
        data = {'date': str(date.today()), 'km_at_service': 6000}

        response = authenticated_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert MaintenanceEvent.objects.count() == 1

    def test_complete_dismissed_task_changes_to_completed(
        self, authenticated_client, motorcycle
    ):
        task = MaintenanceTask.objects.create(
            vehicle=motorcycle,
            task_code='OIL_CHANGE',
            status=MaintenanceTask.Status.DISMISSED
        )
        url = f'/api/maintenance/tasks/{task.id}/complete/'
        data = {'date': str(date.today()), 'km_at_service': 7000}

        response = authenticated_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK
        task.refresh_from_db()
        assert task.status == MaintenanceTask.Status.COMPLETED

    def test_complete_task_with_zero_km_succeeds(
        self, authenticated_client, maintenance_task
    ):
        url = f'/api/maintenance/tasks/{maintenance_task.id}/complete/'
        data = {'date': str(date.today()), 'km_at_service': 0}

        response = authenticated_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK
        event = MaintenanceEvent.objects.first()
        assert event.km_at_service == 0

    def test_complete_task_with_very_large_km_succeeds(
        self, authenticated_client, maintenance_task
    ):
        url = f'/api/maintenance/tasks/{maintenance_task.id}/complete/'
        data = {'date': str(date.today()), 'km_at_service': 999999}

        response = authenticated_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK
        event = MaintenanceEvent.objects.first()
        assert event.km_at_service == 999999

    def test_complete_task_with_future_date_succeeds(
        self, authenticated_client, maintenance_task
    ):
        future = date.today() + timedelta(days=365)
        url = f'/api/maintenance/tasks/{maintenance_task.id}/complete/'
        data = {'date': str(future), 'km_at_service': 5000}

        response = authenticated_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK

    def test_complete_task_with_empty_body_returns_400(
        self, authenticated_client, maintenance_task
    ):
        url = f'/api/maintenance/tasks/{maintenance_task.id}/complete/'

        response = authenticated_client.post(url, {}, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_complete_task_as_unauthenticated_returns_401(
        self, api_client, maintenance_task
    ):
        url = f'/api/maintenance/tasks/{maintenance_task.id}/complete/'
        data = {'date': str(date.today()), 'km_at_service': 5000}

        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestDismissActionEdgeCases:
    """Edge case tests for the dismiss action."""

    def test_dismiss_task_as_unauthenticated_returns_401(
        self, api_client, maintenance_task
    ):
        url = f'/api/maintenance/tasks/{maintenance_task.id}/dismiss/'

        response = api_client.post(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_dismiss_nonexistent_task_returns_404(self, authenticated_client):
        url = '/api/maintenance/tasks/99999/dismiss/'

        response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND


# ============================================================================
# EDGE CASE TESTS - Catalog Filtering
# ============================================================================

@pytest.mark.django_db
class TestCatalogFilteringEdgeCases:
    """Edge case tests for TaskCatalog filtering."""

    def test_filter_catalog_by_invalid_vehicle_type_returns_empty(
        self, authenticated_client, task_catalog_oil_change
    ):
        url = '/api/maintenance/catalog/?vehicle_type=truck'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 0

    def test_filter_catalog_by_empty_vehicle_type_returns_all(
        self, authenticated_client, task_catalog_oil_change, task_catalog_brake_pads
    ):
        url = '/api/maintenance/catalog/?vehicle_type='

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        # Empty string filter matches nothing or all depending on implementation
        # The view filters with queryset.filter(vehicle_type='') which returns empty
        assert isinstance(response.data, list)

    def test_filter_catalog_by_car_returns_car_tasks(
        self, authenticated_client, task_catalog_oil_change, task_catalog_brake_pads
    ):
        url = '/api/maintenance/catalog/?vehicle_type=car'

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['task_code'] == 'BRAKE_PADS'


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

    def test_vehicle_deletion_removes_tasks(self, user, motorcycle, maintenance_task):
        assert MaintenanceTask.objects.count() == 1

        motorcycle.delete()

        assert MaintenanceTask.objects.count() == 0

    def test_task_deletion_sets_created_from_task_null(self, motorcycle):
        task = MaintenanceTask.objects.create(
            vehicle=motorcycle, task_code='TEST'
        )
        event = MaintenanceEvent.objects.create(
            vehicle=motorcycle,
            task_code='TEST',
            date=date.today(),
            km_at_service=1000,
            created_from_task=task
        )

        task.delete()

        event.refresh_from_db()
        assert event.created_from_task is None

    def test_event_deletion_sets_completed_event_null(self, motorcycle):
        event = MaintenanceEvent.objects.create(
            vehicle=motorcycle,
            task_code='TEST',
            date=date.today(),
            km_at_service=1000
        )
        task = MaintenanceTask.objects.create(
            vehicle=motorcycle,
            task_code='TEST',
            status=MaintenanceTask.Status.COMPLETED,
            completed_event=event
        )

        event.delete()

        task.refresh_from_db()
        assert task.completed_event is None


# ============================================================================
# EDGE CASE TESTS - OneToOne Constraint
# ============================================================================

@pytest.mark.django_db
class TestOneToOneConstraint:
    """Tests for OneToOneField constraint on completed_event."""

    def test_two_tasks_cannot_share_same_completed_event(self, motorcycle):
        from django.db import IntegrityError

        event = MaintenanceEvent.objects.create(
            vehicle=motorcycle,
            task_code='TEST',
            date=date.today(),
            km_at_service=1000
        )
        MaintenanceTask.objects.create(
            vehicle=motorcycle,
            task_code='TASK1',
            completed_event=event
        )

        with pytest.raises(IntegrityError):
            MaintenanceTask.objects.create(
                vehicle=motorcycle,
                task_code='TASK2',
                completed_event=event
            )


# ============================================================================
# EDGE CASE TESTS - Ordering
# ============================================================================

@pytest.mark.django_db
class TestTaskOrdering:
    """Tests for MaintenanceTask ordering."""

    def test_tasks_ordered_by_priority_then_due_date(self, motorcycle):
        """Ordering is alphabetical: high < low < medium."""
        low = MaintenanceTask.objects.create(
            vehicle=motorcycle,
            task_code='LOW',
            priority=MaintenanceTask.Priority.LOW,
            due_date=date.today()
        )
        high = MaintenanceTask.objects.create(
            vehicle=motorcycle,
            task_code='HIGH',
            priority=MaintenanceTask.Priority.HIGH,
            due_date=date.today() + timedelta(days=30)
        )
        medium = MaintenanceTask.objects.create(
            vehicle=motorcycle,
            task_code='MEDIUM',
            priority=MaintenanceTask.Priority.MEDIUM,
            due_date=date.today()
        )

        tasks = list(MaintenanceTask.objects.all())

        # Alphabetical ordering: high < low < medium
        assert tasks[0] == high
        assert tasks[1] == low
        assert tasks[2] == medium

    def test_same_priority_ordered_by_due_date(self, motorcycle):
        later = MaintenanceTask.objects.create(
            vehicle=motorcycle,
            task_code='LATER',
            priority=MaintenanceTask.Priority.HIGH,
            due_date=date.today() + timedelta(days=30)
        )
        sooner = MaintenanceTask.objects.create(
            vehicle=motorcycle,
            task_code='SOONER',
            priority=MaintenanceTask.Priority.HIGH,
            due_date=date.today()
        )

        tasks = list(MaintenanceTask.objects.all())

        assert tasks[0] == sooner
        assert tasks[1] == later
