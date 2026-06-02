from google.adk.agents import Agent

from .config import WORKER_MODEL
from .prompt import ASSISTANT
from .language import tutor as language_tutor

agent = Agent(
    name="assistant",
    model=WORKER_MODEL,
    instruction=ASSISTANT,
    sub_agents=[language_tutor],
)
