"""
Comprehensive test suite for the users app.

Tests cover:
- CustomUser model functionality
- UserSerializer and UserCreateSerializer
- UserViewSet endpoints (create, list, retrieve, update, delete, me)
"""

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from rest_framework import status
from rest_framework.test import APIClient
from .models import CustomUser
from .serializers import UserSerializer, UserCreateSerializer

User = get_user_model()


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def api_client():
    """Provide an unauthenticated API client."""
    return APIClient()


@pytest.fixture
def user_data():
    """Provide standard user data for tests."""
    return {
        'email': 'testuser@example.com',
        'username': 'testuser',
        'password': 'securepassword123',
        'first_name': 'Test',
        'last_name': 'User'
    }


@pytest.fixture
@pytest.mark.django_db
def user(user_data):
    """Create and return a standard user instance."""
    user = User.objects.create_user(
        email=user_data['email'],
        username=user_data['username'],
        password=user_data['password'],
        first_name=user_data['first_name'],
        last_name=user_data['last_name']
    )
    return user


@pytest.fixture
def authenticated_client(api_client, user):
    """Provide an authenticated API client."""
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
@pytest.mark.django_db
def another_user():
    """Create and return a second user instance for multi-user tests."""
    return User.objects.create_user(
        email='another@example.com',
        username='anotheruser',
        password='anotherpass123',
        first_name='Another',
        last_name='User'
    )


# =============================================================================
# MODEL TESTS - CustomUser
# =============================================================================


@pytest.mark.django_db
class TestCustomUserModel:
    """Tests for CustomUser model functionality."""

    def test_create_user_with_email_and_username_succeeds(self, user_data):
        """Test creating a user with valid email and username."""
        # Arrange & Act
        user = User.objects.create_user(
            email=user_data['email'],
            username=user_data['username'],
            password=user_data['password']
        )

        # Assert
        assert user.email == user_data['email']
        assert user.username == user_data['username']
        assert user.check_password(user_data['password'])
        assert user.is_active is True
        assert user.is_staff is False
        assert user.is_superuser is False

    def test_create_user_with_email_sets_username_field(self, user_data):
        """Test that email is the USERNAME_FIELD for authentication."""
        # Arrange & Act
        user = User.objects.create_user(
            email=user_data['email'],
            username=user_data['username'],
            password=user_data['password']
        )

        # Assert
        assert User.USERNAME_FIELD == 'email'
        assert user.get_username() == user_data['email']

    def test_create_user_with_duplicate_email_raises_integrity_error(self, user):
        """Test that duplicate emails are not allowed."""
        # Arrange
        duplicate_email = user.email

        # Act & Assert
        with pytest.raises(IntegrityError):
            User.objects.create_user(
                email=duplicate_email,
                username='differentusername',
                password='password123'
            )

    def test_user_str_representation_returns_email(self, user):
        """Test that __str__ method returns the user's email."""
        # Act
        result = str(user)

        # Assert
        assert result == user.email

    def test_create_superuser_sets_staff_and_superuser_flags(self, user_data):
        """Test that create_superuser sets is_staff and is_superuser to True."""
        # Arrange & Act
        superuser = User.objects.create_superuser(
            email='admin@example.com',
            username='admin',
            password='adminpass123'
        )

        # Assert
        assert superuser.is_staff is True
        assert superuser.is_superuser is True
        assert superuser.is_active is True

    def test_user_model_uses_custom_table_name(self):
        """Test that the model uses 'users' as the database table name."""
        # Assert
        assert CustomUser._meta.db_table == 'users'

    def test_user_required_fields_includes_username(self):
        """Test that username is in REQUIRED_FIELDS."""
        # Assert
        assert 'username' in User.REQUIRED_FIELDS

    def test_create_user_with_first_and_last_name_succeeds(self, user_data):
        """Test creating a user with first and last name."""
        # Arrange & Act
        user = User.objects.create_user(
            email=user_data['email'],
            username=user_data['username'],
            password=user_data['password'],
            first_name=user_data['first_name'],
            last_name=user_data['last_name']
        )

        # Assert
        assert user.first_name == user_data['first_name']
        assert user.last_name == user_data['last_name']


# =============================================================================
# SERIALIZER TESTS - UserSerializer
# =============================================================================


@pytest.mark.django_db
class TestUserSerializer:
    """Tests for UserSerializer."""

    def test_serialize_user_includes_all_fields(self, user):
        """Test that serialization includes all expected fields."""
        # Arrange
        serializer = UserSerializer(user)

        # Act
        data = serializer.data

        # Assert
        expected_fields = {'id', 'email', 'username', 'first_name', 'last_name', 'date_joined'}
        assert set(data.keys()) == expected_fields
        assert data['email'] == user.email
        assert data['username'] == user.username
        assert data['first_name'] == user.first_name
        assert data['last_name'] == user.last_name

    def test_serialize_user_excludes_password_field(self, user):
        """Test that password is not included in serialization."""
        # Arrange
        serializer = UserSerializer(user)

        # Act
        data = serializer.data

        # Assert
        assert 'password' not in data

    def test_deserialize_user_with_valid_data_succeeds(self, user):
        """Test updating user with valid data."""
        # Arrange
        update_data = {
            'first_name': 'Updated',
            'last_name': 'Name'
        }
        serializer = UserSerializer(user, data=update_data, partial=True)

        # Act
        is_valid = serializer.is_valid()

        # Assert
        assert is_valid is True
        updated_user = serializer.save()
        assert updated_user.first_name == 'Updated'
        assert updated_user.last_name == 'Name'

    def test_id_and_date_joined_are_read_only(self, user):
        """Test that id and date_joined cannot be modified."""
        # Arrange
        original_id = user.id
        original_date = user.date_joined
        update_data = {
            'id': 999,
            'date_joined': '2020-01-01T00:00:00Z',
            'first_name': 'Updated'
        }
        serializer = UserSerializer(user, data=update_data, partial=True)

        # Act
        serializer.is_valid(raise_exception=True)
        updated_user = serializer.save()

        # Assert
        assert updated_user.id == original_id
        assert updated_user.date_joined == original_date
        assert updated_user.first_name == 'Updated'


# =============================================================================
# SERIALIZER TESTS - UserCreateSerializer
# =============================================================================


@pytest.mark.django_db
class TestUserCreateSerializer:
    """Tests for UserCreateSerializer."""

    def test_create_user_with_valid_data_succeeds(self, user_data):
        """Test creating a user with valid data."""
        # Arrange
        serializer = UserCreateSerializer(data=user_data)

        # Act
        is_valid = serializer.is_valid()

        # Assert
        assert is_valid is True
        user = serializer.save()
        assert user.email == user_data['email']
        assert user.username == user_data['username']
        assert user.check_password(user_data['password'])
        assert user.first_name == user_data['first_name']
        assert user.last_name == user_data['last_name']

    def test_create_user_with_short_password_fails_validation(self):
        """Test that password must be at least 8 characters."""
        # Arrange
        data = {
            'email': 'test@example.com',
            'username': 'testuser',
            'password': 'short',  # Only 5 characters
            'first_name': 'Test',
            'last_name': 'User'
        }
        serializer = UserCreateSerializer(data=data)

        # Act
        is_valid = serializer.is_valid()

        # Assert
        assert is_valid is False
        assert 'password' in serializer.errors
        assert 'at least 8 characters' in str(serializer.errors['password'][0]).lower()

    def test_create_user_without_required_fields_fails_validation(self):
        """Test that required fields cannot be omitted."""
        # Arrange
        data = {
            'email': 'test@example.com',
            # Missing username and password
        }
        serializer = UserCreateSerializer(data=data)

        # Act
        is_valid = serializer.is_valid()

        # Assert
        assert is_valid is False
        assert 'username' in serializer.errors
        assert 'password' in serializer.errors

    def test_create_user_with_invalid_email_fails_validation(self):
        """Test that invalid email format fails validation."""
        # Arrange
        data = {
            'email': 'not-an-email',
            'username': 'testuser',
            'password': 'securepass123'
        }
        serializer = UserCreateSerializer(data=data)

        # Act
        is_valid = serializer.is_valid()

        # Assert
        assert is_valid is False
        assert 'email' in serializer.errors

    def test_serialized_user_excludes_password(self, user_data):
        """Test that password is not exposed in serialized output."""
        # Arrange
        serializer = UserCreateSerializer(data=user_data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Act
        output_serializer = UserCreateSerializer(user)
        data = output_serializer.data

        # Assert
        assert 'password' not in data

    def test_password_is_hashed_not_stored_plaintext(self, user_data):
        """Test that password is properly hashed."""
        # Arrange
        serializer = UserCreateSerializer(data=user_data)
        serializer.is_valid(raise_exception=True)

        # Act
        user = serializer.save()

        # Assert
        assert user.password != user_data['password']
        assert user.password.startswith('pbkdf2_sha256$')
        assert user.check_password(user_data['password'])


# =============================================================================
# VIEW TESTS - UserViewSet (Create - Public)
# =============================================================================


@pytest.mark.django_db
class TestUserViewSetCreate:
    """Tests for UserViewSet create action (public endpoint)."""

    def test_create_user_without_authentication_succeeds(self, api_client, user_data):
        """Test that user creation is allowed without authentication."""
        # Arrange
        url = '/api/users/'

        # Act
        response = api_client.post(url, user_data, format='json')

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['email'] == user_data['email']
        assert response.data['username'] == user_data['username']
        assert 'password' not in response.data
        assert User.objects.filter(email=user_data['email']).exists()

    def test_create_user_with_missing_password_fails(self, api_client):
        """Test that password is required for user creation."""
        # Arrange
        url = '/api/users/'
        data = {
            'email': 'test@example.com',
            'username': 'testuser'
            # Missing password
        }

        # Act
        response = api_client.post(url, data, format='json')

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'password' in response.data

    def test_create_user_with_duplicate_email_fails(self, api_client, user, user_data):
        """Test that duplicate email addresses are rejected."""
        # Arrange
        url = '/api/users/'
        duplicate_data = {
            'email': user.email,  # Use existing user's email
            'username': 'differentusername',
            'password': 'password123'
        }

        # Act
        response = api_client.post(url, duplicate_data, format='json')

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'email' in response.data

    def test_create_user_with_short_password_fails(self, api_client):
        """Test that short passwords are rejected."""
        # Arrange
        url = '/api/users/'
        data = {
            'email': 'test@example.com',
            'username': 'testuser',
            'password': 'short'
        }

        # Act
        response = api_client.post(url, data, format='json')

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'password' in response.data


# =============================================================================
# VIEW TESTS - UserViewSet (List - Authenticated)
# =============================================================================


@pytest.mark.django_db
class TestUserViewSetList:
    """Tests for UserViewSet list action (requires authentication)."""

    def test_list_users_without_authentication_fails(self, api_client):
        """Test that listing users requires authentication."""
        # Arrange
        url = '/api/users/'

        # Act
        response = api_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_users_with_authentication_succeeds(self, authenticated_client, user):
        """Test that authenticated users can list users."""
        # Arrange
        url = '/api/users/'

        # Act
        response = authenticated_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list) or 'results' in response.data

    def test_list_users_returns_all_users(self, authenticated_client, user, another_user):
        """Test that list endpoint returns all users."""
        # Arrange
        url = '/api/users/'

        # Act
        response = authenticated_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        # Handle both paginated and non-paginated responses
        results = response.data if isinstance(response.data, list) else response.data['results']
        assert len(results) >= 2
        emails = [u['email'] for u in results]
        assert user.email in emails
        assert another_user.email in emails


# =============================================================================
# VIEW TESTS - UserViewSet (Retrieve - Authenticated)
# =============================================================================


@pytest.mark.django_db
class TestUserViewSetRetrieve:
    """Tests for UserViewSet retrieve action (requires authentication)."""

    def test_retrieve_user_without_authentication_fails(self, api_client, user):
        """Test that retrieving a user requires authentication."""
        # Arrange
        url = f'/api/users/{user.id}/'

        # Act
        response = api_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_retrieve_user_with_authentication_succeeds(self, authenticated_client, user):
        """Test that authenticated users can retrieve user details."""
        # Arrange
        url = f'/api/users/{user.id}/'

        # Act
        response = authenticated_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == user.id
        assert response.data['email'] == user.email
        assert response.data['username'] == user.username
        assert 'password' not in response.data

    def test_retrieve_nonexistent_user_returns_404(self, authenticated_client):
        """Test that retrieving a non-existent user returns 404."""
        # Arrange
        url = '/api/users/99999/'

        # Act
        response = authenticated_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND


# =============================================================================
# VIEW TESTS - UserViewSet (Update - Authenticated)
# =============================================================================


@pytest.mark.django_db
class TestUserViewSetUpdate:
    """Tests for UserViewSet update actions (requires authentication)."""

    def test_update_user_without_authentication_fails(self, api_client, user):
        """Test that updating a user requires authentication."""
        # Arrange
        url = f'/api/users/{user.id}/'
        data = {'first_name': 'Updated'}

        # Act
        response = api_client.patch(url, data, format='json')

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_partial_update_user_with_authentication_succeeds(self, authenticated_client, user):
        """Test that authenticated users can partially update user data."""
        # Arrange
        url = f'/api/users/{user.id}/'
        data = {
            'first_name': 'UpdatedFirst',
            'last_name': 'UpdatedLast'
        }

        # Act
        response = authenticated_client.patch(url, data, format='json')

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['first_name'] == 'UpdatedFirst'
        assert response.data['last_name'] == 'UpdatedLast'

        # Verify database was updated
        user.refresh_from_db()
        assert user.first_name == 'UpdatedFirst'
        assert user.last_name == 'UpdatedLast'

    def test_full_update_user_with_authentication_succeeds(self, authenticated_client, user):
        """Test full update of user data."""
        # Arrange
        url = f'/api/users/{user.id}/'
        data = {
            'email': user.email,  # Email must be included for full update
            'username': user.username,  # Username must be included
            'first_name': 'CompletelyNew',
            'last_name': 'Name'
        }

        # Act
        response = authenticated_client.put(url, data, format='json')

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['first_name'] == 'CompletelyNew'
        assert response.data['last_name'] == 'Name'


# =============================================================================
# VIEW TESTS - UserViewSet (Delete - Authenticated)
# =============================================================================


@pytest.mark.django_db
class TestUserViewSetDelete:
    """Tests for UserViewSet delete action (requires authentication)."""

    def test_delete_user_without_authentication_fails(self, api_client, user):
        """Test that deleting a user requires authentication."""
        # Arrange
        url = f'/api/users/{user.id}/'

        # Act
        response = api_client.delete(url)

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_delete_user_with_authentication_succeeds(self, authenticated_client, another_user):
        """Test that authenticated users can delete users."""
        # Arrange
        url = f'/api/users/{another_user.id}/'
        user_id = another_user.id

        # Act
        response = authenticated_client.delete(url)

        # Assert
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not User.objects.filter(id=user_id).exists()


# =============================================================================
# VIEW TESTS - UserViewSet (Me Endpoint - Authenticated)
# =============================================================================


@pytest.mark.django_db
class TestUserViewSetMeEndpoint:
    """Tests for UserViewSet me() custom action."""

    def test_me_endpoint_without_authentication_fails(self, api_client):
        """Test that /me endpoint requires authentication."""
        # Arrange
        url = '/api/users/me/'

        # Act
        response = api_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_me_endpoint_with_authentication_returns_current_user(self, authenticated_client, user):
        """Test that /me endpoint returns the authenticated user's data."""
        # Arrange
        url = '/api/users/me/'

        # Act
        response = authenticated_client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == user.id
        assert response.data['email'] == user.email
        assert response.data['username'] == user.username
        assert response.data['first_name'] == user.first_name
        assert response.data['last_name'] == user.last_name
        assert 'password' not in response.data

    def test_me_endpoint_with_different_users_returns_correct_user(
        self, api_client, user, another_user
    ):
        """Test that /me endpoint returns different data for different authenticated users."""
        # Arrange
        url = '/api/users/me/'

        # Act - First user
        api_client.force_authenticate(user=user)
        response1 = api_client.get(url)

        # Act - Second user
        api_client.force_authenticate(user=another_user)
        response2 = api_client.get(url)

        # Assert
        assert response1.status_code == status.HTTP_200_OK
        assert response2.status_code == status.HTTP_200_OK
        assert response1.data['id'] == user.id
        assert response2.data['id'] == another_user.id
        assert response1.data['email'] != response2.data['email']


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


@pytest.mark.django_db
class TestUserWorkflows:
    """Integration tests for common user workflows."""

    def test_complete_user_registration_and_profile_update_workflow(self, api_client):
        """Test full workflow: register -> login -> view profile -> update profile."""
        # Step 1: Register a new user (public endpoint)
        register_url = '/api/users/'
        register_data = {
            'email': 'newuser@example.com',
            'username': 'newuser',
            'password': 'securepass123',
            'first_name': 'New',
            'last_name': 'User'
        }
        register_response = api_client.post(register_url, register_data, format='json')
        assert register_response.status_code == status.HTTP_201_CREATED
        user_id = register_response.data['id']

        # Step 2: Authenticate as the new user
        user = User.objects.get(id=user_id)
        api_client.force_authenticate(user=user)

        # Step 3: View own profile via /me endpoint
        me_url = '/api/users/me/'
        me_response = api_client.get(me_url)
        assert me_response.status_code == status.HTTP_200_OK
        assert me_response.data['email'] == 'newuser@example.com'

        # Step 4: Update profile
        update_url = f'/api/users/{user_id}/'
        update_data = {
            'first_name': 'Updated',
            'last_name': 'Name'
        }
        update_response = api_client.patch(update_url, update_data, format='json')
        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.data['first_name'] == 'Updated'

        # Step 5: Verify update via /me endpoint
        me_response_after = api_client.get(me_url)
        assert me_response_after.data['first_name'] == 'Updated'
        assert me_response_after.data['last_name'] == 'Name'

    def test_user_cannot_be_created_with_duplicate_username(self, api_client, user):
        """Test that duplicate usernames are rejected."""
        # Arrange
        url = '/api/users/'
        data = {
            'email': 'different@example.com',
            'username': user.username,  # Duplicate username
            'password': 'password123'
        }

        # Act
        response = api_client.post(url, data, format='json')

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'username' in response.data
