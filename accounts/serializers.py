from django.contrib.auth import get_user_model
from rest_framework import serializers
from django.conf import settings
from huami.models import HuamiAccount

class HuamiSerializer(serializers.ModelSerializer):
    class Meta:
        model = HuamiAccount
        fields = ['full_name', 'note', 'sync_date']

class UserSerializer(serializers.ModelSerializer):
    huami = HuamiSerializer(read_only=True)
    class Meta:
        model = get_user_model()
        fields = ['id', 'username', 'huami']