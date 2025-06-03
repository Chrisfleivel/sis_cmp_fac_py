#fac/apps.py
from django.apps import AppConfig


class FacConfig(AppConfig):
    name = 'fac'
    
#    def ready(self):
#        import fac.signals # Asegúrate de que tus signals estén en un archivo separado o en models.py
