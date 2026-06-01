import os
from google.adk.models.lite_llm import LiteLlm

OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'localhost')
API_BASE=f"http://{OLLAMA_HOST}:11434"

WORKER_MODEL = LiteLlm(
    model="ollama_chat/gemma4:31b",
    api_base=API_BASE,
)

# WORKER_MODEL = "gemini-2.5-flash"
