from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService


class TutorRunner(Runner):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("app_name", "app")
        kwargs.setdefault("session_service", InMemorySessionService())
        super().__init__(*args, **kwargs)
        # Custom tracking, logging, or state adjustments go here
        print("Tutor Runner intercepted the web session!")
