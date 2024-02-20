from django.contrib.auth import get_user_model
from accounts.serializers import UserSerializer
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, BasePermission
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes


class IsAdminOrReadOnly(BasePermission):
    """User가 superuser일 때만 list 액션 허용
    """    
    def has_permission(self, request, view):
        if view.action == 'list':
            return request.user and request.user.is_superuser


class IsAdminOrOwner(BasePermission):
    """user가 superuser이거나 본인일때만 retrieve 액션 허용
    """    
    def has_object_permission(self, request, view, obj):
        return request.user and (request.user.is_superuser or obj == request.user)


def TokenAuthOpenApiParameter():
    return OpenApiParameter(name='Authorization', type=OpenApiTypes.STR, location=OpenApiParameter.HEADER, description="토큰을 입력하세요.", required=True, default="Token your-token")


@extend_schema_view(
    list=extend_schema(
        description="유저 정보들을 제공합니다.",
        parameters=[
            TokenAuthOpenApiParameter()
        ]
    ),
    retrieve=extend_schema(
        description="id와 일치하는 유저의 정보를 제공합니다",
        parameters=[
            TokenAuthOpenApiParameter()
        ]
    )
)
class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """유저 리스트 혹은 개별 유저 데이터 반환
    """    
    queryset = get_user_model().objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_permissions(self):
        if self.action == 'retrieve':
            return [IsAuthenticated(), IsAdminOrOwner()]
        return super().get_permissions()
