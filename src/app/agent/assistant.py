from google.adk.agents import Agent

from app.corpus_singleton import get_corpus
from app.tools.canvas_tool import make_canvas_delivery_tool
from app.tools.document_search_tool import make_document_search_tool

from .config import WORKER_MODEL
from .language import tutor as language_tutor
from .prompt import ASSISTANT

_corpus = get_corpus()

agent = Agent(
    name="assistant",
    model=WORKER_MODEL,
    instruction=ASSISTANT,
    sub_agents=[language_tutor],
    tools=[
        make_document_search_tool(_corpus),
        make_canvas_delivery_tool(),
    ],
)
