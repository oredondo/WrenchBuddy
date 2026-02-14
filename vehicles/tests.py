import pytest
from unittest.mock import Mock
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from datetime import datetime

from .models import Vehicle
from .serializers import VehicleSerializer, VehicleListSerializer


User = get_user_model()


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def user(db):
    """Create a standard test user."""
    return User.objects.create_user(
        email='testuser@example.com',
        password='testpass123',
        username='testuser'
    )


@pytest.fixture
def another_user(db):
    """Create another user to test isolation."""
    return User.objects.create_user(
        email='anotheruser@example.com',
        password='testpass123',
        username='anotheruser'
    )


@pytest.fixture
def api_client():
    """Create an API client for making requests."""
    return APIClient()


@pytest.fixture
def authenticated_client(api_client, user):
    """Create an authenticated API client."""
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def vehicle_data():
    """Standard vehicle data for testing."""
    return {
        'vehicle_type': 'motorcycle',
        'brand': 'Honda',
        'model': 'CBR600RR',
        'year': 2020,
        'current_km': 5000,
        'displacement': 600,
        'usage_type': 'mixed',
        'notes': 'Test vehicle'
    }


@pytest.fixture
def motorcycle(user):
    """Create a motorcycle for the test user."""
    return Vehicle.objects.create(
        user=user,
        vehicle_type=Vehicle.VehicleType.MOTORCYCLE,
        brand='Yamaha',
        model='YZF-R1',
        year=2019,
        current_km=10000,
        displacement=1000,
        usage_type=Vehicle.UsageType.MIXED,
        notes='Fast bike'
    )


@pytest.fixture
def car(user):
    """Create a car for the test user."""
    return Vehicle.objects.create(
        user=user,
        vehicle_type=Vehicle.VehicleType.CAR,
        brand='Toyota',
        model='Corolla',
        year=2021,
        current_km=25000,
        displacement=1600,
        usage_type=Vehicle.UsageType.CITY,
        notes='Daily driver'
    )


@pytest.fixture
def another_user_vehicle(another_user):
    """Create a vehicle for another user to test isolation."""
    return Vehicle.objects.create(
        user=another_user,
        vehicle_type=Vehicle.VehicleType.MOTORCYCLE,
        brand='Ducati',
        model='Panigale V4',
        year=2022,
        current_km=3000,
        displacement=1103,
        usage_type=Vehicle.UsageType.HIGHWAY
    )


# ============================================================================
# MODEL TESTS
# ============================================================================

@pytest.mark.django_db
class TestVehicleModel:
    """Tests for the Vehicle model."""

    def test_create_motorcycle_with_valid_data_succeeds(self, user):
        """Test creating a motorcycle with all required fields."""
        # Arrange
        vehicle = Vehicle.objects.create(
            user=user,
            vehicle_type=Vehicle.VehicleType.MOTORCYCLE,
            brand='Kawasaki',
            model='Ninja 650',
            year=2023,
            current_km=1000,
            displacement=650,
            usage_type=Vehicle.UsageType.MIXED
        )

        # Assert
        assert vehicle.id is not None
        assert vehicle.user == user
        assert vehicle.vehicle_type == Vehicle.VehicleType.MOTORCYCLE
        assert vehicle.brand == 'Kawasaki'
        assert vehicle.model == 'Ninja 650'
        assert vehicle.year == 2023
        assert vehicle.current_km == 1000
        assert vehicle.displacement == 650
        assert vehicle.usage_type == Vehicle.UsageType.MIXED

    def test_create_car_with_valid_data_succeeds(self, user):
        """Test creating a car with all required fields."""
        # Arrange & Act
        vehicle = Vehicle.objects.create(
            user=user,
            vehicle_type=Vehicle.VehicleType.CAR,
            brand='Ford',
            model='Mustang',
            year=2022,
            current_km=15000,
            displacement=5000,
            usage_type=Vehicle.UsageType.HIGHWAY
        )

        # Assert
        assert vehicle.vehicle_type == Vehicle.VehicleType.CAR
        assert vehicle.brand == 'Ford'
        assert vehicle.model == 'Mustang'

    def test_vehicle_str_representation_returns_formatted_string(self, motorcycle):
        """Test the string representation of a vehicle."""
        # Act
        result = str(motorcycle)

        # Assert
        assert result == "Yamaha YZF-R1 (2019)"

    def test_vehicle_type_choices_are_valid(self):
        """Test that vehicle type choices are correctly defined."""
        # Assert
        assert Vehicle.VehicleType.MOTORCYCLE == 'motorcycle'
        assert Vehicle.VehicleType.CAR == 'car'
        assert len(Vehicle.VehicleType.choices) == 2

    def test_usage_type_choices_are_valid(self):
        """Test that usage type choices are correctly defined."""
        # Assert
        assert Vehicle.UsageType.CITY == 'city'
        assert Vehicle.UsageType.MIXED == 'mixed'
        assert Vehicle.UsageType.HIGHWAY == 'highway'
        assert len(Vehicle.UsageType.choices) == 3

    def test_vehicle_with_default_vehicle_type_is_motorcycle(self, user):
        """Test that default vehicle type is motorcycle."""
        # Act
        vehicle = Vehicle.objects.create(
            user=user,
            brand='Generic',
            model='Model',
            year=2020,
            current_km=0
        )

        # Assert
        assert vehicle.vehicle_type == Vehicle.VehicleType.MOTORCYCLE

    def test_vehicle_with_default_usage_type_is_mixed(self, user):
        """Test that default usage type is mixed."""
        # Act
        vehicle = Vehicle.objects.create(
            user=user,
            brand='Generic',
            model='Model',
            year=2020,
            current_km=0
        )

        # Assert
        assert vehicle.usage_type == Vehicle.UsageType.MIXED

    def test_vehicle_displacement_can_be_null(self, user):
        """Test that displacement field can be null."""
        # Act
        vehicle = Vehicle.objects.create(
            user=user,
            brand='Generic',
            model='Model',
            year=2020,
            current_km=0,
            displacement=None
        )

        # Assert
        assert vehicle.displacement is None

    def test_vehicle_notes_can_be_empty(self, user):
        """Test that notes field can be empty."""
        # Act
        vehicle = Vehicle.objects.create(
            user=user,
            brand='Generic',
            model='Model',
            year=2020,
            current_km=0,
            notes=''
        )

        # Assert
        assert vehicle.notes == ''

    def test_vehicle_has_created_at_timestamp(self, motorcycle):
        """Test that vehicle has created_at timestamp."""
        # Assert
        assert motorcycle.created_at is not None
        assert isinstance(motorcycle.created_at, datetime)

    def test_vehicle_has_updated_at_timestamp(self, motorcycle):
        """Test that vehicle has updated_at timestamp."""
        # Assert
        assert motorcycle.updated_at is not None
        assert isinstance(motorcycle.updated_at, datetime)

    def test_vehicles_ordered_by_created_at_desc(self, user):
        """Test that vehicles are ordered by created_at descending."""
        # Arrange - Create vehicles in specific order
        vehicle1 = Vehicle.objects.create(
            user=user,
            brand='First',
            model='Model1',
            year=2020,
            current_km=0
        )
        vehicle2 = Vehicle.objects.create(
            user=user,
            brand='Second',
            model='Model2',
            year=2021,
            current_km=0
        )

        # Act
        vehicles = list(Vehicle.objects.filter(user=user))

        # Assert - Most recent first
        assert vehicles[0].id == vehicle2.id
        assert vehicles[1].id == vehicle1.id

    def test_deleting_user_cascades_to_vehicles(self, user, motorcycle):
        """Test that deleting a user deletes their vehicles."""
        # Arrange
        vehicle_id = motorcycle.id

        # Act
        user.delete()

        # Assert
        assert not Vehicle.objects.filter(id=vehicle_id).exists()

    def test_user_can_have_multiple_vehicles(self, user):
        """Test that a user can own multiple vehicles."""
        # Arrange & Act
        Vehicle.objects.create(
            user=user,
            brand='Brand1',
            model='Model1',
            year=2020,
            current_km=0
        )
        Vehicle.objects.create(
            user=user,
            brand='Brand2',
            model='Model2',
            year=2021,
            current_km=0
        )

        # Assert
        assert user.vehicles.count() == 2


# ============================================================================
# SERIALIZER TESTS
# ============================================================================

@pytest.mark.django_db
class TestVehicleSerializer:
    """Tests for VehicleSerializer."""

    def test_serialize_vehicle_returns_all_fields(self, motorcycle):
        """Test that serializer includes all expected fields."""
        # Act
        serializer = VehicleSerializer(motorcycle)

        # Assert
        assert 'id' in serializer.data
        assert 'vehicle_type' in serializer.data
        assert 'brand' in serializer.data
        assert 'model' in serializer.data
        assert 'year' in serializer.data
        assert 'current_km' in serializer.data
        assert 'displacement' in serializer.data
        assert 'usage_type' in serializer.data
        assert 'notes' in serializer.data
        assert 'created_at' in serializer.data
        assert 'updated_at' in serializer.data
        # User should not be in serialized data
        assert 'user' not in serializer.data

    def test_serialize_vehicle_contains_correct_values(self, motorcycle):
        """Test that serialized data contains correct values."""
        # Act
        serializer = VehicleSerializer(motorcycle)

        # Assert
        assert serializer.data['vehicle_type'] == 'motorcycle'
        assert serializer.data['brand'] == 'Yamaha'
        assert serializer.data['model'] == 'YZF-R1'
        assert serializer.data['year'] == 2019
        assert serializer.data['current_km'] == 10000
        assert serializer.data['displacement'] == 1000
        assert serializer.data['usage_type'] == 'mixed'
        assert serializer.data['notes'] == 'Fast bike'

    def test_deserialize_valid_data_creates_valid_object(self, vehicle_data, user):
        """Test deserializing valid data creates a valid vehicle."""
        # Arrange
        mock_request = Mock()
        mock_request.user = user
        context = {'request': mock_request}

        # Act
        serializer = VehicleSerializer(data=vehicle_data, context=context)

        # Assert
        assert serializer.is_valid()
        vehicle = serializer.save()
        assert vehicle.user == user
        assert vehicle.brand == 'Honda'
        assert vehicle.model == 'CBR600RR'

    def test_deserialize_with_missing_required_field_is_invalid(self, user):
        """Test that missing required fields make serializer invalid."""
        # Arrange
        mock_request = Mock()
        mock_request.user = user
        context = {'request': mock_request}
        invalid_data = {
            'vehicle_type': 'motorcycle',
            # Missing brand, model, year, current_km
        }

        # Act
        serializer = VehicleSerializer(data=invalid_data, context=context)

        # Assert
        assert not serializer.is_valid()
        assert 'brand' in serializer.errors
        assert 'model' in serializer.errors
        assert 'year' in serializer.errors
        assert 'current_km' in serializer.errors

    def test_deserialize_with_invalid_vehicle_type_is_invalid(self, vehicle_data, user):
        """Test that invalid vehicle type makes serializer invalid."""
        # Arrange
        mock_request = Mock()
        mock_request.user = user
        context = {'request': mock_request}
        vehicle_data['vehicle_type'] = 'invalid_type'

        # Act
        serializer = VehicleSerializer(data=vehicle_data, context=context)

        # Assert
        assert not serializer.is_valid()
        assert 'vehicle_type' in serializer.errors

    def test_deserialize_with_invalid_usage_type_is_invalid(self, vehicle_data, user):
        """Test that invalid usage type makes serializer invalid."""
        # Arrange
        mock_request = Mock()
        mock_request.user = user
        context = {'request': mock_request}
        vehicle_data['usage_type'] = 'invalid_usage'

        # Act
        serializer = VehicleSerializer(data=vehicle_data, context=context)

        # Assert
        assert not serializer.is_valid()
        assert 'usage_type' in serializer.errors

    def test_deserialize_with_negative_year_is_invalid(self, vehicle_data, user):
        """Test that negative year makes serializer invalid."""
        # Arrange
        mock_request = Mock()
        mock_request.user = user
        context = {'request': mock_request}
        vehicle_data['year'] = -2020

        # Act
        serializer = VehicleSerializer(data=vehicle_data, context=context)

        # Assert
        assert not serializer.is_valid()
        assert 'year' in serializer.errors

    def test_deserialize_with_negative_km_is_invalid(self, vehicle_data, user):
        """Test that negative kilometers makes serializer invalid."""
        # Arrange
        mock_request = Mock()
        mock_request.user = user
        context = {'request': mock_request}
        vehicle_data['current_km'] = -1000

        # Act
        serializer = VehicleSerializer(data=vehicle_data, context=context)

        # Assert
        assert not serializer.is_valid()
        assert 'current_km' in serializer.errors

    def test_create_method_sets_user_from_request(self, vehicle_data, user):
        """Test that create method sets user from request context."""
        # Arrange
        mock_request = Mock()
        mock_request.user = user
        context = {'request': mock_request}

        # Act
        serializer = VehicleSerializer(data=vehicle_data, context=context)
        assert serializer.is_valid()
        vehicle = serializer.save()

        # Assert
        assert vehicle.user == user

    def test_read_only_fields_cannot_be_set(self, motorcycle, vehicle_data, user):
        """Test that read-only fields are not updated."""
        # Arrange
        mock_request = Mock()
        mock_request.user = user
        context = {'request': mock_request}
        original_id = motorcycle.id
        original_created = motorcycle.created_at

        update_data = vehicle_data.copy()
        update_data['id'] = 99999
        update_data['created_at'] = '2000-01-01T00:00:00Z'

        # Act
        serializer = VehicleSerializer(motorcycle, data=update_data, context=context)
        assert serializer.is_valid()
        updated_vehicle = serializer.save()

        # Assert
        assert updated_vehicle.id == original_id
        assert updated_vehicle.created_at == original_created


@pytest.mark.django_db
class TestVehicleListSerializer:
    """Tests for VehicleListSerializer."""

    def test_serialize_vehicle_returns_only_list_fields(self, motorcycle):
        """Test that list serializer only includes minimal fields."""
        # Act
        serializer = VehicleListSerializer(motorcycle)

        # Assert
        expected_fields = {'id', 'vehicle_type', 'brand', 'model', 'year', 'current_km'}
        assert set(serializer.data.keys()) == expected_fields

    def test_serialize_vehicle_excludes_detailed_fields(self, motorcycle):
        """Test that list serializer excludes detailed fields."""
        # Act
        serializer = VehicleListSerializer(motorcycle)

        # Assert
        assert 'displacement' not in serializer.data
        assert 'usage_type' not in serializer.data
        assert 'notes' not in serializer.data
        assert 'created_at' not in serializer.data
        assert 'updated_at' not in serializer.data

    def test_serialize_multiple_vehicles_returns_list(self, user):
        """Test serializing multiple vehicles."""
        # Arrange
        Vehicle.objects.create(
            user=user,
            brand='Brand1',
            model='Model1',
            year=2020,
            current_km=1000
        )
        Vehicle.objects.create(
            user=user,
            brand='Brand2',
            model='Model2',
            year=2021,
            current_km=2000
        )
        vehicles = Vehicle.objects.filter(user=user)

        # Act
        serializer = VehicleListSerializer(vehicles, many=True)

        # Assert
        assert len(serializer.data) == 2
        assert all('brand' in item for item in serializer.data)
        assert all('notes' not in item for item in serializer.data)


# ============================================================================
# VIEW/VIEWSET TESTS
# ============================================================================

@pytest.mark.django_db
class TestVehicleViewSet:
    """Tests for VehicleViewSet."""

    def test_list_vehicles_unauthenticated_returns_401(self, api_client):
        """Test that unauthenticated requests are rejected."""
        # Act
        response = api_client.get('/api/vehicles/')

        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_vehicles_authenticated_returns_200(self, authenticated_client):
        """Test that authenticated users can list vehicles."""
        # Act
        response = authenticated_client.get('/api/vehicles/')

        # Assert
        assert response.status_code == status.HTTP_200_OK

    def test_list_vehicles_returns_only_user_vehicles(
        self, authenticated_client, motorcycle, car, another_user_vehicle
    ):
        """Test that users only see their own vehicles."""
        # Act
        response = authenticated_client.get('/api/vehicles/')

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2
        vehicle_ids = [v['id'] for v in response.data]
        assert motorcycle.id in vehicle_ids
        assert car.id in vehicle_ids
        assert another_user_vehicle.id not in vehicle_ids

    def test_list_vehicles_uses_list_serializer(self, authenticated_client, motorcycle):
        """Test that list action uses VehicleListSerializer."""
        # Act
        response = authenticated_client.get('/api/vehicles/')

        # Assert
        assert response.status_code == status.HTTP_200_OK
        vehicle_data = response.data[0]
        # Should have list fields
        assert 'id' in vehicle_data
        assert 'brand' in vehicle_data
        # Should not have detail fields
        assert 'notes' not in vehicle_data
        assert 'created_at' not in vehicle_data

    def test_retrieve_vehicle_returns_full_details(self, authenticated_client, motorcycle):
        """Test that retrieve action returns full vehicle details."""
        # Act
        response = authenticated_client.get(f'/api/vehicles/{motorcycle.id}/')

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == motorcycle.id
        assert response.data['brand'] == 'Yamaha'
        assert response.data['model'] == 'YZF-R1'
        # Should have all detailed fields
        assert 'notes' in response.data
        assert 'created_at' in response.data
        assert 'updated_at' in response.data
        assert 'displacement' in response.data

    def test_retrieve_another_user_vehicle_returns_404(
        self, authenticated_client, another_user_vehicle
    ):
        """Test that users cannot retrieve other users' vehicles."""
        # Act
        response = authenticated_client.get(f'/api/vehicles/{another_user_vehicle.id}/')

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_vehicle_with_valid_data_returns_201(
        self, authenticated_client, vehicle_data
    ):
        """Test creating a vehicle with valid data."""
        # Act
        response = authenticated_client.post('/api/vehicles/', vehicle_data, format='json')

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['brand'] == 'Honda'
        assert response.data['model'] == 'CBR600RR'
        assert 'id' in response.data

    def test_create_vehicle_associates_with_authenticated_user(
        self, authenticated_client, user, vehicle_data
    ):
        """Test that created vehicle is associated with authenticated user."""
        # Act
        response = authenticated_client.post('/api/vehicles/', vehicle_data, format='json')

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        vehicle_id = response.data['id']
        vehicle = Vehicle.objects.get(id=vehicle_id)
        assert vehicle.user == user

    def test_create_vehicle_with_missing_fields_returns_400(self, authenticated_client):
        """Test that creating vehicle with missing fields fails."""
        # Arrange
        invalid_data = {
            'brand': 'Honda',
            # Missing required fields
        }

        # Act
        response = authenticated_client.post('/api/vehicles/', invalid_data, format='json')

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_vehicle_unauthenticated_returns_401(self, api_client, vehicle_data):
        """Test that unauthenticated users cannot create vehicles."""
        # Act
        response = api_client.post('/api/vehicles/', vehicle_data, format='json')

        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_vehicle_with_valid_data_returns_200(
        self, authenticated_client, motorcycle
    ):
        """Test updating a vehicle with valid data."""
        # Arrange
        update_data = {
            'vehicle_type': 'motorcycle',
            'brand': 'Yamaha',
            'model': 'YZF-R1M',  # Updated model
            'year': 2019,
            'current_km': 15000,  # Updated km
            'displacement': 1000,
            'usage_type': 'highway',  # Updated usage
            'notes': 'Updated notes'
        }

        # Act
        response = authenticated_client.put(
            f'/api/vehicles/{motorcycle.id}/',
            update_data,
            format='json'
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['model'] == 'YZF-R1M'
        assert response.data['current_km'] == 15000
        assert response.data['usage_type'] == 'highway'

    def test_partial_update_vehicle_returns_200(self, authenticated_client, motorcycle):
        """Test partial update of a vehicle."""
        # Arrange
        partial_data = {
            'current_km': 12000,
            'notes': 'Partially updated'
        }

        # Act
        response = authenticated_client.patch(
            f'/api/vehicles/{motorcycle.id}/',
            partial_data,
            format='json'
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['current_km'] == 12000
        assert response.data['notes'] == 'Partially updated'
        # Other fields should remain unchanged
        assert response.data['brand'] == 'Yamaha'
        assert response.data['model'] == 'YZF-R1'

    def test_update_another_user_vehicle_returns_404(
        self, authenticated_client, another_user_vehicle
    ):
        """Test that users cannot update other users' vehicles."""
        # Arrange
        update_data = {
            'vehicle_type': 'motorcycle',
            'brand': 'Ducati',
            'model': 'Updated',
            'year': 2022,
            'current_km': 5000
        }

        # Act
        response = authenticated_client.put(
            f'/api/vehicles/{another_user_vehicle.id}/',
            update_data,
            format='json'
        )

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_vehicle_returns_204(self, authenticated_client, motorcycle):
        """Test deleting a vehicle."""
        # Arrange
        vehicle_id = motorcycle.id

        # Act
        response = authenticated_client.delete(f'/api/vehicles/{vehicle_id}/')

        # Assert
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Vehicle.objects.filter(id=vehicle_id).exists()

    def test_delete_another_user_vehicle_returns_404(
        self, authenticated_client, another_user_vehicle
    ):
        """Test that users cannot delete other users' vehicles."""
        # Arrange
        vehicle_id = another_user_vehicle.id

        # Act
        response = authenticated_client.delete(f'/api/vehicles/{vehicle_id}/')

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        # Vehicle should still exist
        assert Vehicle.objects.filter(id=vehicle_id).exists()

    def test_list_empty_vehicles_returns_empty_list(self, authenticated_client):
        """Test listing vehicles when user has none."""
        # Act
        response = authenticated_client.get('/api/vehicles/')

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_queryset_filtered_by_request_user(
        self, authenticated_client, motorcycle, car, another_user_vehicle
    ):
        """Test that queryset is properly filtered by authenticated user."""
        # Act
        response = authenticated_client.get('/api/vehicles/')

        # Assert
        assert response.status_code == status.HTTP_200_OK
        returned_ids = {v['id'] for v in response.data}
        expected_ids = {motorcycle.id, car.id}
        assert returned_ids == expected_ids

    def test_create_multiple_vehicles_for_same_user_succeeds(
        self, authenticated_client, vehicle_data
    ):
        """Test that a user can create multiple vehicles."""
        # Act
        response1 = authenticated_client.post('/api/vehicles/', vehicle_data, format='json')
        vehicle_data['model'] = 'Different Model'
        response2 = authenticated_client.post('/api/vehicles/', vehicle_data, format='json')

        # Assert
        assert response1.status_code == status.HTTP_201_CREATED
        assert response2.status_code == status.HTTP_201_CREATED
        assert response1.data['id'] != response2.data['id']

        # Verify both vehicles exist
        list_response = authenticated_client.get('/api/vehicles/')
        assert len(list_response.data) == 2
