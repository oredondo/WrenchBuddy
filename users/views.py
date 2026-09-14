from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CustomUser
from .serializers import UserSerializer, UserCreateSerializer, PublicUserSerializer


class UserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return UserSerializer

    @action(detail=False, methods=['get'])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['patch'],
            parser_classes=[MultiPartParser, FormParser, JSONParser])
    def update_profile(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def change_password(self, request):
        current = request.data.get('current_password', '')
        new = request.data.get('new_password', '')
        if not current or not new:
            return Response({'message': 'Faltan campos obligatorios.'}, status=status.HTTP_400_BAD_REQUEST)
        if not request.user.check_password(current):
            return Response({'message': 'La contraseña actual no es correcta.'}, status=status.HTTP_400_BAD_REQUEST)
        if len(new) < 8:
            return Response({'message': 'La nueva contraseña debe tener al menos 8 caracteres.'}, status=status.HTTP_400_BAD_REQUEST)
        request.user.set_password(new)
        request.user.save()
        return Response({'detail': 'Contraseña actualizada.'})

    @action(detail=False, methods=['delete'])
    def delete_account(self, request):
        password = request.data.get('password', '')
        if not password:
            return Response({'message': 'Debes confirmar tu contraseña.'}, status=status.HTTP_400_BAD_REQUEST)
        if not request.user.check_password(password):
            return Response({'message': 'Contraseña incorrecta.'}, status=status.HTTP_400_BAD_REQUEST)
        request.user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PublicProfileView(APIView):
    """GET /api/users/profile/<username>/ — perfil público de un usuario."""
    permission_classes = [IsAuthenticated]

    def get(self, request, username):
        user = CustomUser.objects.filter(username=username).first()
        if not user:
            raise NotFound("Usuario no encontrado.")
        return Response(PublicUserSerializer(user, context={'request': request}).data)


@ensure_csrf_cookie
def csrf(request):
    return JsonResponse({"detail": "CSRF cookie set"})
