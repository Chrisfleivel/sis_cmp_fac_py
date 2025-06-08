#fac/admin.py
from django.contrib import admin
from .models import Cliente, FacturaEnc, FacturaDet, Cuenta # Asegúrate de agregar Cuenta

admin.site.register(Cliente)
admin.site.register(FacturaEnc)
admin.site.register(FacturaDet)
admin.site.register(Cuenta) # Registrar el modelo Cuenta