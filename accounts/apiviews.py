from django.contrib.auth import get_user_model
from accounts.serializers import UserSerializer
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, IsAdminUser, BasePermission
from rest_framework.decorators import action

class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if view.action == 'list':
            return request.user and request.user.is_superuser

class IsAdminOrOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user and (request.user.is_superuser or obj == request.user)

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = get_user_model().objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminOrReadOnly]
    
    def get_permissions(self):
        if self.action == 'retrieve':
            return [IsAuthenticated(), IsAdminOrOwner()]
        return super().get_permissions()
    