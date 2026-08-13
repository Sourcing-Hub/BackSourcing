from rest_framework import serializers
from .models import Etape, ParticipationEtape

class EtapeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Etape
        fields = ['id', 'nom', 'ordre']

class ParticipationEtapeSerializer(serializers.ModelSerializer):
    etape_detail = EtapeSerializer(source='etape', read_only=True)
    
    class Meta:
        model = ParticipationEtape
        fields = ['id', 'statut', 'dateEntree', 'dateSortie', 'motif', 'etape', 'etape_detail']
        read_only_fields = ['id', 'dateEntree', 'dateSortie', 'etape']
