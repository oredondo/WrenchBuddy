from django.apps import AppConfig


class VehiclesConfig(AppConfig):
    name = 'vehicles'

    def ready(self):
        import vehicles.signals  # noqa
