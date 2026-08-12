from django.contrib import admin
from .models import Utilisateur, Role


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['nom', 'description']
    search_fields = ['nom']


@admin.register(Utilisateur)
class UtilisateurAdmin(admin.ModelAdmin):
    list_display = [
        'email', 'first_name', 'last_name',
        'get_role', 'statut', 'compteActive', 'profilComplet', 'dateCreation'
    ]
    list_filter = ['role', 'statut', 'compteActive', 'profilComplet']
    search_fields = ['email', 'first_name', 'last_name']
    readonly_fields = ['id', 'dateCreation', 'dateModification', 'tokenActivation', 'tokenExpiration']
    ordering = ['-dateCreation']

    fieldsets = (
        ('Informations personnelles', {
            'fields': ('id', 'first_name', 'last_name', 'email', 'username', 'telephone', 'sexe')
        }),
        ('Rôle et statut', {
            'fields': ('role', 'statut', 'compteActive', 'profilComplet', 'is_active', 'is_staff', 'is_superuser')
        }),
        ('Activation du compte', {
            'fields': ('tokenActivation', 'tokenExpiration'),
            'classes': ('collapse',),
        }),
        ('Dates', {
            'fields': ('dateCreation', 'dateModification', 'last_login'),
            'classes': ('collapse',),
        }),
    )

    def get_role(self, obj):
        return obj.role.nom if obj.role else '—'
    get_role.short_description = 'Rôle'
