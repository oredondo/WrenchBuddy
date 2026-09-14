from django.apps import AppConfig


class AiAssistantConfig(AppConfig):
    name = 'ai_assistant'

    def ready(self):
        from ai_assistant.signals import attachment_analysis_completed
        from ai_assistant.handlers import handle_analysis_completed

        attachment_analysis_completed.connect(handle_analysis_completed)
