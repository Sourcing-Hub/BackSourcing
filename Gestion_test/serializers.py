from rest_framework import serializers
from .models import Test

class TestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Test
        fields = '__all__' # Pour commencer, on expose tous les champs du modèle
        
    # Optionnel : Tu pourras ajouter ici des validations personnalisées plus tard
    # par exemple, vérifier la taille du fichier ou le format de l'URL