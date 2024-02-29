from django.contrib.auth import get_user_model
from rest_framework import serializers
from django.conf import settings
from huami.models import HuamiAccount
from huami.models.healthdata import HealthData

class HuamiHealthSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthData
        fields = ['date', 'info_status']

class HuamiSerializer(serializers.ModelSerializer):
    last_health_info = HuamiHealthSerializer()
    
    class Meta:
        model = HuamiAccount
        fields = ['full_name', 'note', 'sync_date', 'last_health_info']

class UserSerializer(serializers.ModelSerializer):
    huami = HuamiSerializer(read_only=True)
    class Meta:
        model = get_user_model()
        fields = ['id', 'username', 'huami']
        
class NormalUserSerializer(serializers.ModelSerializer):
    huami = HuamiSerializer()
    class Meta:
        model = get_user_model()
        fields = ['id', 'username', 'huami']