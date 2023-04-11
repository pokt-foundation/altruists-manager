from rest_framework import serializers
from .models import Chain, Altruist
from django.contrib.auth.models import User
# import datetime
# from django.utils import timezone

class AltruistSerializer(serializers.ModelSerializer):
    owner = serializers.CharField(source='owner.username',)
    chain_id = serializers.CharField(max_length=4,source='chain_id.chain_id')
    url = serializers.CharField()

    class Meta:
        model = Altruist
        ordering = ['chain_id','url']
        fields = ['owner', 'chain_id', 'url']

