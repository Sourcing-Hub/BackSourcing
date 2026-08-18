from rest_framework import serializers
from .models import Test
from .models import SoumissionTest

class TestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Test
        fields = '__all__' # Pour commencer, on expose tous les champs du modèle
        
    # Optionnel : Tu pourras ajouter ici des validations personnalisées plus tard
    # par exemple, vérifier la taille du fichier ou le format de l'URL

   

class SoumissionTestSerializer(serializers.ModelSerializer):
    class Meta:
        model = SoumissionTest
        fields = ['id', 'nom_candidat', 'email_candidat', 'fichier_test', 'date_soumission']
        read_only_fields = ['id', 'date_soumission']