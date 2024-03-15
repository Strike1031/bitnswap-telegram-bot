from rest_framework import serializers
from .models import UserInfo


class PersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserInfo
        fields = '__all__'
