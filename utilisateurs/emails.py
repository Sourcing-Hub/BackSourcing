"""
Service d'envoi d'emails pour la gestion des utilisateurs.
En développement, les emails s'affichent dans la console.
"""
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string


def _url_frontend(chemin: str) -> str:
    base = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
    return f"{base.rstrip('/')}/{chemin.lstrip('/')}"


def envoyer_email_invitation_personnel(utilisateur):
    """
    Envoyé par l'administrateur lorsqu'il crée un compte personnel
    (Équipe Pédagogique ou Équipe Gestion de Projet).
    Le contenu de l'email est personnalisé selon le rôle de l'utilisateur.
    """
    from utilisateurs.models import NomRole

    lien = _url_frontend(f"auth/activer/{utilisateur.tokenActivation}")
    role_nom = utilisateur.role.nom if utilisateur.role else "Personnel"
    delai = getattr(settings, 'DELAI_ACTIVATION_TOKEN_HEURES', 48)

    # ── Personnalisation selon le rôle ──────────────────────────
    if utilisateur.role and utilisateur.role.nom == NomRole.EQUIPE_PEDAGOGIQUE:
        sujet = "[SourcingHub] Bienvenue dans l'Équipe Pédagogique !"
        intro = (
            "Vous rejoignez l'Équipe Pédagogique de SourcingHub. "
            "Votre rôle consiste à piloter le parcours de sélection des candidats : "
            "gestion des évaluateurs, suivi des entretiens et validation des candidatures."
        )
        responsabilites = (
            "  • Créer et gérer les évaluateurs\n"
            "  • Suivre et noter les candidatures\n"
            "  • Superviser les étapes d'évaluation\n"
            "  • Piloter les campagnes de recrutement"
        )

    elif utilisateur.role and utilisateur.role.nom == NomRole.EQUIPE_GESTION_PROJET:
        sujet = "[SourcingHub] Bienvenue dans l'Équipe Gestion de Projet !"
        intro = (
            "Vous rejoignez l'Équipe Gestion de Projet de SourcingHub. "
            "Votre rôle est d'assurer le suivi opérationnel des formations et cohortes : "
            "planification, organisation et coordination des campagnes."
        )
        responsabilites = (
            "  • Gérer les formations et cohortes\n"
            "  • Créer et suivre les campagnes de recrutement\n"
            "  • Consulter et analyser les candidatures\n"
            "  • Coordonner avec les équipes pédagogiques"
        )

    else:
        sujet = f"[SourcingHub] Invitation à rejoindre la plateforme – {role_nom}"
        intro = f"Votre compte SourcingHub a été créé en tant que « {role_nom} »."
        responsabilites = None

    # ── Construction du message ─────────────────────────────────
    corps = (
        f"Bonjour,\n\n"
        f"{intro}\n\n"
    )
    if responsabilites:
        corps += (
            f"Vos responsabilités sur la plateforme :\n"
            f"{responsabilites}\n\n"
        )
    corps += (
        f"Pour activer votre compte et définir votre mot de passe, "
        f"cliquez sur le lien ci-dessous :\n"
        f"{lien}\n\n"
        f"Ce lien est valide pendant {delai} heures.\n\n"
        f"Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.\n\n"
        f"L'équipe SourcingHub"
    )

    send_mail(
        subject=sujet,
        message=corps,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[utilisateur.email],
        fail_silently=False,
    )



def envoyer_email_invitation_evaluateur(utilisateur, createur):
    """
    Envoyé par l'équipe pédagogique lorsqu'elle crée un compte évaluateur.
    """
    lien = _url_frontend(f"auth/activer/{utilisateur.tokenActivation}")

    sujet = "[SourcingHub] Vous avez été invité en tant qu'Évaluateur"
    message = (
        f"Bonjour,\n\n"
        f"{createur.get_full_name() or createur.email} vous a invité à rejoindre SourcingHub "
        f"en tant qu'Évaluateur.\n\n"
        f"Pour activer votre compte et définir votre mot de passe, cliquez sur le lien ci-dessous :\n"
        f"{lien}\n\n"
        f"Ce lien est valide pendant {getattr(settings, 'DELAI_ACTIVATION_TOKEN_HEURES', 48)} heures.\n\n"
        f"Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.\n\n"
        f"L'équipe SourcingHub"
    )

    send_mail(
        subject=sujet,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[utilisateur.email],
        fail_silently=False,
    )


def envoyer_email_reinitialisation_mdp(utilisateur):
    """
    Envoyé lorsqu'un utilisateur demande la réinitialisation de son mot de passe.
    """
    lien = _url_frontend(f"auth/reinit-mdp/confirmer/{utilisateur.tokenActivation}")

    sujet = "[SourcingHub] Réinitialisation de votre mot de passe"
    message = (
        f"Bonjour {utilisateur.first_name or utilisateur.email},\n\n"
        f"Vous avez demandé la réinitialisation de votre mot de passe SourcingHub.\n\n"
        f"Cliquez sur le lien ci-dessous pour définir un nouveau mot de passe :\n"
        f"{lien}\n\n"
        f"Ce lien est valide pendant {getattr(settings, 'DELAI_ACTIVATION_TOKEN_HEURES', 48)} heures.\n\n"
        f"Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.\n\n"
        f"L'équipe SourcingHub"
    )

    send_mail(
        subject=sujet,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[utilisateur.email],
        fail_silently=False,
    )


def envoyer_email_activation_candidat(utilisateur):
    """
    Envoyé au candidat après sa soumission de candidature s'il n'a pas de compte.
    """
    lien = _url_frontend(f"auth/activer/{utilisateur.tokenActivation}")

    sujet = "[SourcingHub] Activation de votre compte Candidat"
    message = (
        f"Bonjour {utilisateur.first_name},\n\n"
        f"Merci d'avoir postulé sur SourcingHub.\n"
        f"Votre compte candidat a été créé automatiquement. "
        f"Pour activer votre compte et suivre l'état de votre candidature, veuillez cliquer sur le lien ci-dessous :\n"
        f"{lien}\n\n"
        f"Ce lien est valide pendant {getattr(settings, 'DELAI_ACTIVATION_TOKEN_HEURES', 48)} heures.\n\n"
        f"L'équipe SourcingHub"
    )

    send_mail(
        subject=sujet,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[utilisateur.email],
        fail_silently=False,
    )

