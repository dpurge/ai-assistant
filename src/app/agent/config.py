from google.adk.models.lite_llm import LiteLlm

from app.config import get_settings

_settings = get_settings()

WORKER_MODEL = LiteLlm(
    model=_settings.ollama_model,
    api_base=_settings.ollama_api_base,
)
