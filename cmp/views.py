#cmp/views.py

from django.shortcuts import render,redirect
from django.views import generic
from django.urls import reverse_lazy
import datetime
from datetime import date
from django.http import HttpResponse, JsonResponse
import json # Importar json para manejar JSONField
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth import authenticate
from django.http import HttpResponse
from django.db.models import Sum

from .models import Proveedor, ComprasEnc, ComprasDet, CuentaPagar # Importar CuentaPagar
from cmp.forms import ProveedorForm,ComprasEncForm
from bases.views import SinPrivilegios
from inv.models import Producto


class ProveedorView(SinPrivilegios, generic.ListView):
    model = Proveedor
    template_name = "cmp/proveedor_list.html"
    context_object_name = "obj"
    permission_required="cmp.view_proveedor"

class ProveedorNew(SuccessMessageMixin, SinPrivilegios,\
                   generic.CreateView):
    model=Proveedor
    template_name="cmp/proveedor_form.html"
    context_object_name = 'obj'
    form_class=ProveedorForm
    success_url= reverse_lazy("cmp:proveedor_list")
    success_message="Proveedor Nuevo"
    permission_required="cmp.add_proveedor"

    def form_valid(self, form):
        form.instance.uc = self.request.user
        #print(self.request.user.id)
        return super().form_valid(form)


class ProveedorEdit(SuccessMessageMixin, SinPrivilegios,\
                   generic.UpdateView):
    model=Proveedor
    template_name="cmp/proveedor_form.html"
    context_object_name = 'obj'
    form_class=ProveedorForm
    success_url= reverse_lazy("cmp:proveedor_list")
    success_message="Proveedor Actualizado"
    permission_required="cmp.change_proveedor"

    def form_valid(self, form):
        form.instance.um = self.request.user.id
        return super().form_valid(form)

@login_required(login_url='/login/')
@permission_required('cmp.change_proveedor', login_url='sin_privilegios')
def proveedorInactivar(request,id):
    proveedor = Proveedor.objects.filter(pk=id).first()
    if request.method=="GET":
        context = {'obj':proveedor}
        return render(request,'cmp/proveedor_inactivar.html',context)
    
    if request.method=="POST":
        proveedor.estado = not proveedor.estado
        proveedor.save()
        return HttpResponse("OK")
    return HttpResponse("OK")


class ComprasView(SinPrivilegios, generic.ListView):
    model = ComprasEnc
    template_name = "cmp/compras_list.html"
    context_object_name = "obj"
    permission_required = "cmp.view_comprasenc"


@login_required(login_url='/login/')
@permission_required('cmp.view_comprasenc', login_url='sin_privilegios')
def compras(request, compra_id=None):
    if compra_id:
        # Vista de edición/detalle
        template_name = "cmp/compras_productos.html"
        enc = ComprasEnc.objects.filter(pk=compra_id).first()
        if not enc:
            messages.error(request, "Compra no existe")
            return redirect("cmp:compras_list")
        form_compras = ComprasEncForm(instance=enc)
        productos = Producto.objects.filter(estado=True)
        detalles = ComprasDet.objects.filter(compra=enc)
        cuotas = CuentaPagar.objects.filter(compra=enc).order_by('fecha_vencimiento')

        if request.method == "POST":
            form_compras = ComprasEncForm(request.POST, instance=enc)
            if form_compras.is_valid():
                enc = form_compras.save(commit=False)
                enc.um = request.user.id
                if enc.tipo_pago == 'CR' and enc.tipo_cuota == 'I':
                    num = int(request.POST.get('num_cuotas', 0))
                    dias = []
                    for i in range(1, num+1):
                        dias.append(int(request.POST.get(f'dias_cuota_{i}', 0)))
                    enc.dias_vencimiento_irregular = dias
                enc.save()
                messages.success(request, "Encabezado actualizado correctamente.")
                return redirect("cmp:compras_edit", compra_id=enc.id)
            else:
                print(form_compras.errors)
                messages.error(request, "Error al actualizar el encabezado.")

        contexto = {
            'obj': enc,
            'form_enc': form_compras,
            'productos': productos,
            'detalles': detalles,
            'cuotas': cuotas,
        }
        return render(request, template_name, contexto)

    else:
        # Vista de nuevo encabezado
        template_name = "cmp/compras.html"
        form_compras = ComprasEncForm()
        if request.method == "POST":
            form_compras = ComprasEncForm(request.POST)
            if form_compras.is_valid():
                enc = form_compras.save(commit=False)
                enc.uc = request.user
                enc.um = request.user.id
                enc.save()
                messages.success(request, "Compra guardada correctamente.")
                return redirect("cmp:compras_edit", compra_id=enc.id)
            else:
                print(form_compras.errors)
                messages.error(request, "Error al guardar la compra. Revise los campos.")

        contexto = {
            'form_enc': form_compras,
        }
        return render(request, template_name, contexto)

@login_required(login_url='/login/')
@permission_required('cmp.view_comprasenc', login_url='sin_privilegios')
def compras2(request, compra_id=None):
    template_name = "cmp/compras.html"
    prod = Producto.objects.filter(estado=True)
    form_compras = None
    enc = None
    det = None
    cuotas = None

    if request.method == "GET":
        if compra_id:
            enc = ComprasEnc.objects.filter(pk=compra_id).first()
            if not enc:
                messages.error(request, "Compra no existe")
                return redirect("cmp:compras_list")
            cuotas = CuentaPagar.objects.filter(compra=enc).order_by('fecha_vencimiento')
            form_compras = ComprasEncForm(instance=enc)
            det = ComprasDet.objects.filter(compra=enc)
        else:
            form_compras = ComprasEncForm()
            # No mostrar detalles ni productos si aún no existe encabezado

    if request.method == "POST":
        data = request.POST.copy()
        # Manejar JSONField si aplica
        dias_irregulares_str = data.get('dias_vencimiento_irregular', '')
        if dias_irregulares_str:
            try:
                data['dias_vencimiento_irregular'] = json.loads(dias_irregulares_str)
            except json.JSONDecodeError:
                data['dias_vencimiento_irregular'] = []
                messages.error(request, "Formato de días irregulares inválido. Debe ser una lista JSON (ej: [30, 60, 90])")
        else:
            data['dias_vencimiento_irregular'] = []

        if compra_id:
            enc = ComprasEnc.objects.filter(pk=compra_id).first()
            if not enc:
                messages.error(request, "Compra no existe")
                return redirect("cmp:compras_list")
            form_compras = ComprasEncForm(data, instance=enc)
        else:
            form_compras = ComprasEncForm(data)

        if form_compras.is_valid():
            enc = form_compras.save(commit=False)
            if not compra_id:
                enc.uc = request.user
            enc.um = request.user.id
            enc.save()
            messages.success(request, "Compra guardada correctamente.")
            # Redirige a edición para permitir agregar productos
            return redirect("cmp:compras_edit", compra_id=enc.id)
        else:
            messages.error(request, "Error al guardar la compra. Revise los campos.")
            print(form_compras.errors)

    contexto = {
        'obj': enc,  # Encabezado de la compra (puede ser None)
        'detalles': det,  # Detalles solo si existe encabezado
        'productos': prod,
        'form_enc': form_compras,
        'cuotas': cuotas
    }
    return render(request, template_name, contexto)

@login_required(login_url='/login/')
@permission_required('cmp.delete_comprasdet', login_url='sin_privilegios')
def borrar_detalle_compra(request, compra_id, pk):
    template_name = "cmp/compras_borrar_detalle.html"
    det = ComprasDet.objects.get(pk=pk)
    if request.method == "GET":
        context = {'det': det}
        return render(request, template_name, context)

    if request.method == "POST":
        usr = request.POST.get("usuario")
        pas = request.POST.get("password")

        user = authenticate(username=usr, password=pas)
        if not user:
            return HttpResponse("Usuario o Contraseña Incorrecta")
        
        if not user.is_superuser:
            return HttpResponse("No tiene permisos para esta acción")
        
        det.delete() # El signal se encargará de actualizar los totales
        messages.success(request, "Detalle eliminado correctamente.")
        return redirect('cmp:compras_edit', compra_id=compra_id)



# Vista para marcar una cuota como pagada (opcional, se puede hacer desde el admin también)
@login_required(login_url='/login/')
@permission_required('cmp.change_cuentapagar', login_url='sin_privilegios')
def pagar_cuota(request, cuota_id):
    cuota = CuentaPagar.objects.filter(pk=cuota_id).first()
    if not cuota:
        return JsonResponse({'status': 'error', 'message': 'Cuota no encontrada'})

    if request.method == 'POST':
        if not cuota.pagado:
            cuota.pagado = True
            cuota.fecha_pago = date.today()
            cuota.um = request.user.id # Actualizar usuario que modifica
            cuota.save()
            return JsonResponse({'status': 'ok', 'message': 'Cuota marcada como pagada.'})
        else:
            return JsonResponse({'status': 'error', 'message': 'La cuota ya está pagada.'})
    
    return JsonResponse({'status': 'error', 'message': 'Método no permitido.'})    


@login_required(login_url='/login/')
@permission_required('cmp.add_comprasdet', login_url='sin_privilegios')
def agregar_detalle_compra(request, compra_id):
    if request.method == "POST":
        producto_id = request.POST.get('producto_id')
        cantidad = request.POST.get('cantidad')
        precio = request.POST.get('precio')
        descuento = request.POST.get('descuento', 0)
        compra = ComprasEnc.objects.get(pk=compra_id)
        producto = Producto.objects.get(pk=producto_id)
        ComprasDet.objects.create(
            compra=compra,
            producto=producto,
            cantidad=cantidad,
            precio_prv=precio,
            descuento=descuento,
            uc=request.user,         # <--- Asigna el usuario creador
            um=request.user.id       # <--- Asigna el usuario modificador
        )
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error'}, status=400)

