"""Extraction structurée d'une commande vocale via l'API OpenRouter."""
import json
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings


class OpenRouterError(Exception):
    pass


def extract_slot(text, etapes=(), encadrants=()):
    api_key = getattr(settings, 'OPENROUTER_API_KEY', '')
    if not api_key:
        raise OpenRouterError("L'assistant n'est pas configuré : ajoutez OPENROUTER_API_KEY dans le fichier .env.")
    prompt = (
        f"Date actuelle : {date.today().isoformat()}. Extrait un créneau de recrutement depuis ce texte français. "
        "Réponds avec exactement ces clés JSON : etape, date, heureDebut, heureFin, capacite, lieu, localisation, coachTechnique, coachMotivation. "
        "Utilise YYYY-MM-DD et HH:MM, sans inventer de valeur ; null si absent. "
        f"Étapes autorisées : {', '.join(etapes)}. Encadrants autorisés : {', '.join(encadrants)}. "
        f"Texte : {text}"
    )
    payload = json.dumps({
        'model': getattr(settings, 'OPENROUTER_MODEL', 'openrouter/auto'),
        'messages': [
            {'role': 'system', 'content': 'Réponds uniquement avec l’objet JSON correspondant au schéma fourni.'},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': 0,
        # Compatible avec le modèle rapide sélectionné ; Django valide ensuite les données.
        'response_format': {'type': 'json_object'},
    }).encode('utf-8')
    request = Request('https://openrouter.ai/api/v1/chat/completions', data=payload, headers={
        'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json',
    }, method='POST')
    try:
        with urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
        return json.loads(result['choices'][0]['message']['content'])
    except HTTPError as exc:
        if exc.code in (401, 403):
            raise OpenRouterError("OpenRouter refuse la clé API. Vérifiez OPENROUTER_API_KEY.")
        if exc.code == 429:
            raise OpenRouterError("La limite OpenRouter est atteinte. Réessayez dans quelques instants.")
        raise OpenRouterError(f"OpenRouter a renvoyé l'erreur HTTP {exc.code}.")
    except (URLError, TimeoutError):
        raise OpenRouterError("OpenRouter ne répond pas. Vérifiez votre connexion puis réessayez.")
    except (KeyError, IndexError, json.JSONDecodeError):
        raise OpenRouterError("La réponse OpenRouter est invalide. Réessayez votre commande.")
