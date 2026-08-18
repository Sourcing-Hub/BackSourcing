from rest_framework import serializers
from .models import Test
from .models import SoumissionTest
from django.utils import timezone

class TestSerializer(serializers.ModelSerializer):
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
    