from django.contrib import admin
from .models import Formulaire, ChampFormulaire, OptionChamp


class OptionChampInline(admin.TabularInline):
    model  = OptionChamp
    extra  = 1
    fields = ['libelle', 'valeur', 'ordre']


class ChampFormulaireInline(admin.StackedInline):
    model  = ChampFormulaire
    extra  = 0
    fields = ['libelle', 'type', 'obligatoire', 'ordre', 'regleValidation']
    show_change_link = True


@admin.register(Formulaire)
class FormulaireAdmin(admin.ModelAdmin):
    list_display  = ['titre', 'campagne', 'publie', 'nombre_champs', 'dateCreation']
    list_filter   = ['publie']
    search_fields = ['titre']
    inlines       = [ChampFormulaireInline]
    readonly_fields = ['dateCreation', 'dateModification']

    def nombre_champs(self, obj):
        return obj.champs.count()
    nombre_champs.short_description = 'Nb champs'


@admin.register(ChampFormulaire)
class ChampFormulaireAdmin(admin.ModelAdmin):
    list_display  = ['libelle', 'type', 'formulaire', 'obligatoire', 'ordre']
    list_filter   = ['type', 'obligatoire']
    search_fields = ['libelle']
    inlines       = [OptionChampInline]
