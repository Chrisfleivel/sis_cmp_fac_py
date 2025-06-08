#cmp/admin.py
from django.contrib import admin
from .models import Proveedor, ComprasEnc, ComprasDet, CuentaPagar # Importa el nuevo modelo

class ComprasDetInline(admin.TabularInline):
    model = ComprasDet
    extra = 1
    readonly_fields = ('sub_total', 'total',) # Mostrar pero no permitir edición directa

class CuentaPagarInline(admin.TabularInline):
    model = CuentaPagar
    extra = 0 # No añadir filas vacías por defecto
    readonly_fields = ('importe', 'fecha_vencimiento', 'numero_cuota', 'fecha_pago', 'pagado',) # Solo vista
    can_delete = False # No permitir borrar cuotas desde aquí
    show_change_link = True # Permite ir al detalle de la cuota si se quiere editar manualmente

@admin.register(ComprasEnc)
class ComprasEncAdmin(admin.ModelAdmin):
    inlines = [ComprasDetInline, CuentaPagarInline]
    list_display = (
        'id', 'proveedor', 'fecha_compra', 'no_factura', 'total', 'tipo_pago',
        'num_cuotas', 'tipo_cuota', 'estado', 'uc', 'fc'
    )
    list_filter = ('tipo_pago', 'estado', 'fecha_compra',)
    search_fields = ('id', 'proveedor__descripcion', 'no_factura',)
    readonly_fields = ('sub_total', 'descuento', 'total',) # Estos campos son calculados

    fieldsets = (
        (None, {
            'fields': (('proveedor', 'fecha_compra', 'fecha_factura'),
                       ('no_factura', 'tipo_pago'),
                       ('num_cuotas', 'tipo_cuota', 'dias_vencimiento_irregular'),
                       'observacion',
                       ('sub_total', 'descuento', 'total'),
                       'estado')
        }),
    )

    # Permite al admin guardar el usuario que creó/modificó el registro
    def save_model(self, request, obj, form, change):
        if not change:
            obj.uc = request.user
        obj.um = request.user.id
        super().save_model(request, obj, form, change)


admin.site.register(Proveedor)
#admin.site.register(ComprasEnc) # Se registra con el decorador @admin.register
admin.site.register(ComprasDet) # Se gestiona a través de ComprasEncAdmin inline
admin.site.register(CuentaPagar) # Registrar el nuevo modelo
