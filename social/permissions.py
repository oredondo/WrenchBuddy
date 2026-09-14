from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsOwnerOrPublicReadOnly(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS and obj.is_public:
            return True
        return obj.vehicle.user == request.user
