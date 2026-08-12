from django.contrib import admin
from .models import Formation, Cohorte, Campagne


@admin.register(Formation)
class FormationAdmin(admin.ModelAdmin):
    list_display  = ['nom', 'dateDebut', 'dateFin']
    search_fields = ['nom']


@admin.register(Cohorte)
class CohorteAdmin(admin.ModelAdmin):
    list_display  = ['nom', 'formation', 'dateDebut', 'dateFin']
    list_filter   = ['formation']
    search_fields = ['nom']


@admin.register(Campagne)
class CampagneAdmin(admin.ModelAdmin):
    list_display  = ['nom', 'cohorte', 'statut', 'dateOuverture', 'dateCloture', 'publiee', 'archivee']
    list_filter   = ['statut', 'publiee', 'archivee']
    search_fields = ['nom']
    readonly_fields = ['dateCreation', 'dateModification']
    actions = ['action_ouvrir', 'action_fermer', 'action_archiver']

    def action_ouvrir(self, request, queryset):
        for c in queryset:
            c.ouvrir()
        self.message_user(request, "Campagnes ouvertes.")
    action_ouvrir.short_description = "Ouvrir les campagnes sélectionnées"

    def action_fermer(self, request, queryset):
        for c in queryset:
            c.fermer()
        self.message_user(request, "Campagnes fermées.")
    action_fermer.short_description = "Fermer les campagnes sélectionnées"

    def action_archiver(self, request, queryset):
        for c in queryset:
            c.archiver()
        self.message_user(request, "Campagnes archivées.")
    action_archiver.short_description = "Archiver les campagnes sélectionnées"
