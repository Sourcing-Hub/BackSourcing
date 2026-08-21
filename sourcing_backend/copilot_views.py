"""
Rétrocompatibilité : Redirection vers le module sourcingchat_views.
"""
from sourcing_backend.sourcingchat_views import (
    SourcingChatView as CopilotChatView,
    SourcingChatSuggestionsView as CopilotSuggestionsView,
    get_sourcing_live_context,
    generate_local_fallback_response,
)

__all__ = [
    'CopilotChatView',
    'CopilotSuggestionsView',
    'get_sourcing_live_context',
    'generate_local_fallback_response',
]
