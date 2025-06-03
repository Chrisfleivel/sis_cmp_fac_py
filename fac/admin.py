#fac/admin.py
from django.contrib import admin
from .models import Cliente, FacturaEnc, FacturaDet  # Agrega aquí todos tus modelos de fac

admin.site.register(Cliente)
admin.site.register(FacturaEnc)
admin.site.register(FacturaDet)