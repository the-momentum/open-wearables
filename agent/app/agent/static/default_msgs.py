"""Default fallback messages used throughout the agent, per supported language."""

from app.schemas.language import Language

_WORKFLOW_ERROR_MSGS: dict[Language, str] = {
    Language.english: "I encountered an issue processing your request. Please try again in a moment.",
    Language.polish: "Napotkałem problem z przetworzeniem Twojego zapytania. Spróbuj ponownie za chwilę.",
    Language.german: (
        "Bei der Verarbeitung Ihrer Anfrage ist ein Problem aufgetreten. Bitte versuchen Sie es gleich erneut."
    ),
    Language.spanish: "Encontré un problema al procesar tu solicitud. Por favor, inténtalo de nuevo en un momento.",
}


def get_workflow_error_msg(language: Language | None = None) -> str:
    return _WORKFLOW_ERROR_MSGS.get(language or Language.english, _WORKFLOW_ERROR_MSGS[Language.english])
