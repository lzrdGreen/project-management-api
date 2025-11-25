from django.apps import AppConfig


class ProjectappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'projectapp'

    def ready(self):
        import projectapp.signals  # Ensure your signals are registered
