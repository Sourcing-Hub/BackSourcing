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
    Le destinataire doit cliquer sur le lien pour activer son compte et choisir son mot de passe.
    """
    lien = _url_frontend(f"auth/activer/{utilisateur.tokenActivation}")
    role_nom = utilisateur.role.nom if utilisateur.role else "Personnel"

    sujet = f"[SourcingHub] Invitation à rejoindre la plateforme – {role_nom}"
    message = (
        f"Bonjour,\n\n"
        f"Votre compte SourcingHub a été créé en tant que « {role_nom} ».\n\n"
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
