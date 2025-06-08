#cmp/urls.py

from django.urls import path, include

from .views import ProveedorView,ProveedorNew, ProveedorEdit, \
    proveedorInactivar, \
    ComprasView, compras, borrar_detalle_compra, pagar_cuota, agregar_detalle_compra # Importar pagar_cuota y borrar_detalle_compra

from .reportes import reporte_compras, imprimir_compra

urlpatterns = [
    path('proveedores/',ProveedorView.as_view(), name="proveedor_list"),
    path('proveedores/new',ProveedorNew.as_view(), name="proveedor_new"),
    path('proveedores/edit/<int:pk>',ProveedorEdit.as_view(), name="proveedor_edit"),
    path('proveedores/inactivar/<int:id>',proveedorInactivar, name="proveedor_inactivar"),

    path('compras/',ComprasView.as_view(), name="compras_list"),
    path('compras/new',compras, name="compras_new"),
    path('compras/edit/<int:compra_id>',compras, name="compras_edit"),
    
    # URL para borrar detalles de compra (antes era CompraDetDelete, ahora una función)
    path('compras/<int:compra_id>/delete-detalle/<int:pk>',borrar_detalle_compra, name="compras_del_detalle"),
    
    # Nueva URL para pagar cuotas
    path('compras/cuota/pagar/<int:cuota_id>', pagar_cuota, name='pagar_cuota'),

    path('compras/listado', reporte_compras, name='compras_print_all'),
    path('compras/<int:compra_id>/agregar-detalle', agregar_detalle_compra, name="compras_agregar_detalle"),
    path('compras/<int:compra_id>/imprimir', imprimir_compra,name="compras_print_one"),
]