from rest_framework import serializers

from .models import CustomUser


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'email', 'username', 'first_name', 'last_name',
                  'display_name', 'bio', 'location', 'avatar', 'show_spending', 'date_joined']
        read_only_fields = ['id', 'email', 'username', 'date_joined']


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = CustomUser
        fields = ['id', 'email', 'username', 'password', 'first_name', 'last_name']
        read_only_fields = ['id']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = CustomUser(**validated_data)
        user.set_password(password)
        user.save()
        return user


class PublicUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['username', 'display_name', 'bio', 'location', 'avatar', 'show_spending']
