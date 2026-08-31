from rest_framework import serializers
from .models import Test
from .models import SoumissionTest
from django.utils import timezone
from datetime import datetime

class TestSerializer(serializers.ModelSerializer):

    def to_internal_value(self, data):
        # On intercepte les dates reçues du front au format DD-MM-YYYY pour les passer en YYYY-MM-DD
        mutable_data = data.copy()
        
        for field_name in ['date_ouverture', 'date_cloture']:
            date_str = mutable_data.get(field_name)
            if date_str:
                try:
                    # Convertit "19-08-2026" en objet date, puis en "2026-08-19" pour Django
                    parsed_date = datetime.strptime(date_str, '%d-%m-%Y').date()
                    mutable_data[field_name] = parsed_date.strftime('%Y-%m-%d')
                except ValueError:
                    pass # Laisse Django gérer l'erreur si le format est complètement invalide
                    
        return super().to_internal_value(mutable_data)
    
    class Meta:
        model = Test
        fields = '__all__'



class SoumissionTestSerializer(serializers.ModelSerializer):
    test = serializers.PrimaryKeyRelatedField(queryset=Test.objects.all())

    class Meta:
        model = SoumissionTest
        fields = ['id', 'test', 'nom_candidat', 'email_candidat', 'fichier_test', 'date_soumission']
        read_only_fields = ['id', 'date_soumission']

    def validate(self, data):
        test_associe = data.get('test')
        maintenant = timezone.now()
        
        if test_associe:
            # Vérifier si le test n'a pas encore ouvert
            if test_associe.date_ouverture and maintenant < test_associe.date_ouverture:
                raise serializers.ValidationError(
                    "Ce test n'est pas encore ouvert. Veuillez patienter jusqu'à la date d'ouverture."
                )
            
            # Vérifier si la date de clôture est dépassée
            if test_associe.date_cloture and maintenant > test_associe.date_cloture:
                raise serializers.ValidationError(
                    "La date limite pour soumettre ce test est dépassée. Les soumissions sont fermées."
                )
                
        return data
    