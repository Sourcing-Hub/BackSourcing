from django.urls import path

from .views import (
    FormulaireListeView,
    FormulaireDetailView,
    FormulairePublierView,
    FormulaireDepublierView,
    FormulaireAssocierCampagneView,
    FormulaireReorganiserChampsView,
    FormulairePrevisualisationView,
    FormulairePubliqueCampagneView,
    ChampListeView,
    ChampDetailView,
    OptionListeView,
    OptionDetailView,
)

urlpatterns = [
    # ============================================================
    # FORMULAIRE PUBLIC ASSOCIÉ À UNE CAMPAGNE
    # ============================================================

    path(
        'publique/campagne/<uuid:campagne_id>/',
        FormulairePubliqueCampagneView.as_view(),
        name='formulaires-publique-campagne',
    ),

    # ============================================================
    # FORMULAIRES
    # ============================================================

    path(
        '',
        FormulaireListeView.as_view(),
        name='formulaires-liste',
    ),

    path(
        '<uuid:pk>/',
        FormulaireDetailView.as_view(),
        name='formulaires-detail',
    ),

    path(
        '<uuid:pk>/publier/',
        FormulairePublierView.as_view(),
        name='formulaires-publier',
    ),

    path(
        '<uuid:pk>/depublier/',
        FormulaireDepublierView.as_view(),
        name='formulaires-depublier',
    ),

    path(
        '<uuid:pk>/associer-campagne/',
        FormulaireAssocierCampagneView.as_view(),
        name='formulaires-associer',
    ),

    path(
        '<uuid:pk>/reorganiser-champs/',
        FormulaireReorganiserChampsView.as_view(),
        name='formulaires-reorganiser',
    ),

    path(
        '<uuid:pk>/previsualiser/',
        FormulairePrevisualisationView.as_view(),
        name='formulaires-previsualiser',
    ),

    # ============================================================
    # CHAMPS
    # ============================================================

    path(
        '<uuid:pk>/champs/',
        ChampListeView.as_view(),
        name='champs-liste',
    ),

    path(
        'champs/<uuid:champ_id>/',
        ChampDetailView.as_view(),
        name='champs-detail',
    ),

    # ============================================================
    # OPTIONS
    # ============================================================

    path(
        'champs/<uuid:champ_id>/options/',
        OptionListeView.as_view(),
        name='options-liste',
    ),

    path(
        'options/<uuid:option_id>/',
        OptionDetailView.as_view(),
        name='options-detail',
    ),
]