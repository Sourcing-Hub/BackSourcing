import os
import json
import logging
import requests
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from campagnes.models import Campagne, StatutCampagne, Formation, Cohorte
from candidatures.models import Candidature, StatutCandidature
from evaluations.models import Session, Etape, TestQCM, Evaluation, AffectationCandidat
from utilisateurs.models import Utilisateur, NomRole

logger = logging.getLogger(__name__)


def get_sourcing_live_context(user):
    """
    Extrait et agrège les données réelles de la base de données SourcingHub
    pour nourrir le contexte de l'assistant SourcingChat.
    """
    now = timezone.now()
    today = now.date()

    # 1. Formations & Cohortes
    total_formations = Formation.objects.count()
    formations_liste = list(Formation.objects.values_list('nom', flat=True)[:5])
    total_cohortes = Cohorte.objects.count()

    # 2. Campagnes
    total_campagnes = Campagne.objects.count()
    campagnes_ouvertes_qs = Campagne.objects.filter(statut=StatutCampagne.OUVERTE)
    campagnes_ouvertes_count = campagnes_ouvertes_qs.count()
    campagnes_brouillon_count = Campagne.objects.filter(statut=StatutCampagne.BROUILLON).count()
    campagnes_fermees_count = Campagne.objects.filter(statut=StatutCampagne.FERMEE).count()

    campagnes_actives_details = []
    for c in campagnes_ouvertes_qs.select_related('cohorte', 'cohorte__formation')[:5]:
        campagnes_actives_details.append({
            "nom": c.nom,
            "formation": c.cohorte.formation.nom if c.cohorte and c.cohorte.formation else "Non spécifiée",
            "cohorte": c.cohorte.nom if c.cohorte else "Non spécifiée",
            "cloture": c.dateCloture.strftime('%d/%m/%Y à %H:%M') if c.dateCloture else "Non définie",
            "candidatures_recues": c.candidatures.count()
        })

    # 3. Candidatures
    total_candidatures = Candidature.objects.count()
    candidatures_en_attente = Candidature.objects.filter(statut=StatutCandidature.EN_ATTENTE).count()
    candidatures_en_cours = Candidature.objects.filter(statut=StatutCandidature.EN_COURS).count()
    candidatures_terminees = Candidature.objects.filter(statut=StatutCandidature.TERMINEE).count()

    # 4. Sessions & Entretiens
    total_sessions = Session.objects.count()
    sessions_a_venir = Session.objects.filter(date__gte=today).count()
    sessions_aujourdhui = Session.objects.filter(date=today).count()

    # 5. Tests QCM
    total_tests_qcm = TestQCM.objects.count()
    tests_publies = TestQCM.objects.filter(estPublie=True).count()

    # 6. Utilisateurs & Rôles
    total_utilisateurs = Utilisateur.objects.count()
    total_candidats = Utilisateur.objects.filter(role__nom=NomRole.CANDIDAT).count()
    total_evaluateurs = Utilisateur.objects.filter(role__nom=NomRole.EVALUATEUR).count()

    # Si l'utilisateur est un candidat, on restreint/ajoute ses données personnelles
    user_context = {
        "nom_complet": user.get_full_name() or user.username,
        "role": user.role.nom if user.role else "Utilisateur",
        "email": user.email,
    }

    if user.role and user.role.nom == NomRole.CANDIDAT:
        mes_candidatures = list(Candidature.objects.filter(utilisateur=user).values(
            'numero', 'statut', 'dateSoumission', 'campagne__nom'
        ))
        user_context["mes_candidatures"] = mes_candidatures

    return {
        "date_du_jour": today.strftime('%d/%m/%Y'),
        "heure_actuelle": now.strftime('%H:%M'),
        "demandeur": user_context,
        "statistiques_globales": {
            "formations_totales": total_formations,
            "exemples_formations": formations_liste,
            "cohortes_totales": total_cohortes,
            "campagnes": {
                "total": total_campagnes,
                "ouvertes": campagnes_ouvertes_count,
                "brouillons": campagnes_brouillon_count,
                "fermees": campagnes_fermees_count,
                "liste_ouvertes": campagnes_actives_details,
            },
            "candidatures": {
                "total": total_candidatures,
                "en_attente": candidatures_en_attente,
                "en_cours": candidatures_en_cours,
                "terminees": candidatures_terminees,
            },
            "sessions_et_entretiens": {
                "total_sessions": total_sessions,
                "sessions_a_venir": sessions_a_venir,
                "sessions_aujourdhui": sessions_aujourdhui,
            },
            "tests_qcm": {
                "total": total_tests_qcm,
                "publies": tests_publies,
            },
            "utilisateurs": {
                "total": total_utilisateurs,
                "candidats": total_candidats,
                "evaluateurs": total_evaluateurs,
            }
        }
    }


def generate_local_fallback_response(question: str, context: dict) -> str:
    """
    Fournit une réponse locale intelligente et formatée en Markdown sans emojis
    lorsque l'API LLM distante n'est pas disponible ou qu'aucune clé API n'est configurée.
    """
    q_lower = question.lower()
    stats = context["statistiques_globales"]
    campagnes = stats["campagnes"]
    candidatures = stats["candidatures"]
    sessions = stats["sessions_et_entretiens"]

    if any(word in q_lower for word in ["campagne", "recrutement", "ouverte", "formation"]):
        if campagnes["ouvertes"] > 0:
            lines = [f"Actuellement, il y a **{campagnes['ouvertes']} campagne(s) ouverte(s)** sur SourcingHub :\n"]
            for c in campagnes["liste_ouvertes"]:
                lines.append(f"- **{c['nom']}** ({c['formation']} - {c['cohorte']}) : clôture le {c['cloture']} avec **{c['candidatures_recues']} candidature(s)**.")
            return "\n".join(lines)
        return "Il n'y a actuellement aucune campagne ouverte. Vous pouvez en configurer une nouvelle depuis la section Campagnes."

    if any(word in q_lower for word in ["candidat", "candidature", "dossier", "postulant"]):
        return (
            f"**Statistiques des candidatures SourcingHub** :\n\n"
            f"- **Total des dossiers :** {candidatures['total']}\n"
            f"- **En attente de traitement :** {candidatures['en_attente']}\n"
            f"- **En cours d'évaluation :** {candidatures['en_cours']}\n"
            f"- **Finalisées / Terminées :** {candidatures['terminees']}\n\n"
            f"Vous pouvez consulter la liste complète et filtrer les dossiers dans l'onglet Candidatures."
        )

    if any(word in q_lower for word in ["entretien", "session", "planning", "emargement", "présence", "date"]):
        return (
            f"**Planification des sessions et entretiens** :\n\n"
            f"- **Sessions aujourd'hui :** {sessions['sessions_aujourdhui']}\n"
            f"- **Sessions à venir :** {sessions['sessions_a_venir']}\n"
            f"- **Total des sessions créées :** {sessions['total_sessions']}\n\n"
            f"Rendez-vous dans la rubrique Planification ou Mes entretiens pour gérer les horaires et l'émargement QR Code."
        )

    # Réponse générale / d'ensemble
    return (
        f"Bonjour **{context['demandeur']['nom_complet']}**,\n\n"
        f"Voici l'état en direct de votre plateforme SourcingHub au {context['date_du_jour']} :\n\n"
        f"| Métrique | Valeur |\n"
        f"| :--- | :--- |\n"
        f"| Campagnes actives | **{campagnes['ouvertes']}** (sur {campagnes['total']} totales) |\n"
        f"| Candidatures en cours | **{candidatures['en_cours']}** (sur {candidatures['total']} reçues) |\n"
        f"| Entretiens / Sessions à venir | **{sessions['sessions_a_venir']}** |\n"
        f"| Formations enregistrées | **{stats['formations_totales']}** |\n\n"
        f"*Vous pouvez poser une question précise sur les campagnes, les statistiques de recrutement ou vos sessions.*"
    )


class SourcingChatView(APIView):
    """
    Endpoint principal du SourcingChat IA SourcingHub.
    POST /api/sourcingchat/chat/
    Body: {"question": "texte de la question"}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        question = request.data.get("question", "").strip()
        if not question:
            return Response(
                {"error": "Une question est requise."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 1. Extraction des données réelles de la base
        live_context = get_sourcing_live_context(request.user)

        # 2. Vérification des clés API LLM
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")
        gemini_key = os.getenv("GEMINI_API_KEY")
        llm_model = os.getenv("LLM_MODEL", "google/gemini-2.0-flash-001")

        # Mode secours direct si aucune clé API configurée
        if not openrouter_key and not openai_key and not gemini_key:
            response_text = generate_local_fallback_response(question, live_context)
            return Response({
                "response": response_text,
                "provider": "local_fallback",
                "timestamp": timezone.now().isoformat()
            })

        # 3. Construction du prompt système enrichi
        system_prompt = (
            "Tu es SourcingChat, l'assistant IA officiel de SourcingHub, la plateforme de sourcing et recrutement de talents Simplon.\n"
            "Tu réponds toujours en français, avec un ton professionnel, sobre, clair et structuré.\n"
            "RÈGLE STRICTE ET OBLIGATOIRE : N'utilise ABSOLUMENT AUCUN emoji (aucun pictogramme, aucun smiley, aucun symbole graphique). Reste 100% textuel.\n"
            "Utilise la mise en forme Markdown standard (titres, listes à puces, texte en gras, tableaux si pertinent).\n"
            "Tu as accès aux données exactes et en temps réel de la plateforme fournies ci-dessous.\n"
            "Base tes réponses prioritairement sur ces données et conseille efficacement l'utilisateur."
        )

        user_message_content = (
            f"Question de l'utilisateur : {question}\n\n"
            f"--- DONNÉES SYSTÈME TEMPS RÉEL SOURCINGHUB ---\n"
            f"{json.dumps(live_context, ensure_ascii=False, indent=2)}"
        )

        headers = {"Content-Type": "application/json"}
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message_content}
            ],
            "temperature": 0.3,
            "max_tokens": 800
        }

        # 4. Appel de l'API LLM
        try:
            if openrouter_key:
                headers["Authorization"] = f"Bearer {openrouter_key}"
                headers["HTTP-Referer"] = "http://localhost:5173"
                headers["X-Title"] = "SourcingChat SourcingHub"
                payload["model"] = llm_model
                res = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=25
                )
            elif openai_key:
                headers["Authorization"] = f"Bearer {openai_key}"
                payload["model"] = "gpt-4o-mini"
                res = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=25
                )
            elif gemini_key:
                headers["Authorization"] = f"Bearer {gemini_key}"
                payload["model"] = "gemini-1.5-flash"
                res = requests.post(
                    "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=25
                )

            if res.status_code == 200:
                data = res.json()
                ai_response = data["choices"][0]["message"]["content"]
                return Response({
                    "response": ai_response,
                    "provider": "llm",
                    "timestamp": timezone.now().isoformat()
                })
            else:
                logger.warning(f"LLM API returned error code {res.status_code}: {res.text}")
                fallback = generate_local_fallback_response(question, live_context)
                return Response({
                    "response": fallback,
                    "provider": "local_fallback",
                    "warning": f"LLM API non disponible ({res.status_code}). Réponse générée depuis la base de données.",
                    "timestamp": timezone.now().isoformat()
                })

        except Exception as e:
            logger.error(f"Error calling LLM provider: {str(e)}")
            fallback = generate_local_fallback_response(question, live_context)
            return Response({
                "response": fallback,
                "provider": "local_fallback",
                "warning": "Connexion distante temporairement indisponible. Données extraites en direct de la base.",
                "timestamp": timezone.now().isoformat()
            })


class SourcingChatSuggestionsView(APIView):
    """
    Endpoint retournant une liste de questions rapides suggérées.
    GET /api/sourcingchat/suggestions/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = request.user.role.nom if request.user.role else "Utilisateur"

        if role == NomRole.CANDIDAT:
            suggestions = [
                "Où en est l'évaluation de mon dossier ?",
                "Quelles sont les campagnes ouvertes actuellement ?",
                "Comment se déroulent les tests et entretiens ?",
            ]
        elif role == NomRole.EVALUATEUR:
            suggestions = [
                "Combien d'entretiens sont programmés aujourd'hui ?",
                "Quels sont les candidats que je dois évaluer ?",
                "Résume l'état des présences aux sessions.",
            ]
        else:
            suggestions = [
                "Combien de candidatures sont actuellement en cours ?",
                "Quelles sont les campagnes actuellement ouvertes ?",
                "Résume les statistiques globales du sourcing aujourd'hui.",
                "Combien de sessions et d'entretiens sont prévus ?",
            ]

        return Response({"suggestions": suggestions})


# Alias pour rétrocompatibilité
CopilotChatView = SourcingChatView
CopilotSuggestionsView = SourcingChatSuggestionsView
