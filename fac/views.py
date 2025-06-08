#fac/views.py

from django.shortcuts import render,redirect
from django.views import generic

from django.views.decorators.csrf import csrf_exempt

from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse, JsonResponse
from datetime import datetime, date
from django.contrib import messages

from django.contrib.auth import authenticate

from bases.views import SinPrivilegios

from .models import Cliente, FacturaEnc, FacturaDet, Cuenta # Importar el nuevo modelo Cuenta
from .forms import ClienteForm, CuentaForm # Asegúrate de importar CuentaForm
import inv.views as inv
from inv.models import Producto

from django.db.models import Q # Para filtros complejos

class ClienteView(SinPrivilegios, generic.ListView):
    model = Cliente
    template_name = "fac/cliente_list.html"
    context_object_name = "obj"
    permission_required="cmp.view_cliente"


class VistaBaseCreate(SuccessMessageMixin,SinPrivilegios, \
    generic.CreateView):
    context_object_name = 'obj'
    success_message="Registro Agregado Satisfactoriamente"

    def form_valid(self, form):
        form.instance.uc = self.request.user
        return super().form_valid(form)

class VistaBaseEdit(SuccessMessageMixin,SinPrivilegios, \
    generic.UpdateView):
    context_object_name = 'obj'
    success_message="Registro Actualizado Satisfactoriamente"

    def form_valid(self, form):
        form.instance.um = self.request.user.id
        return super().form_valid(form)


class ClienteNew(VistaBaseCreate):
    model=Cliente
    template_name="fac/cliente_form.html"
    form_class=ClienteForm
    success_url= reverse_lazy("fac:cliente_list")
    permission_required="fac.add_cliente"

    def get(self, request, *args, **kwargs):
        print("sobre escribir get")
        
        try:
            t = request.GET["t"]
        except:
            t = None

        print(t)
        
        form = self.form_class(initial=self.initial)
        return render(request, self.template_name, {'form': form, 't':t})


class ClienteEdit(VistaBaseEdit):
    model=Cliente
    template_name="fac/cliente_form.html"
    form_class=ClienteForm
    success_url= reverse_lazy("fac:cliente_list")
    permission_required="fac.change_cliente"

    def get(self, request, *args, **kwargs):
        print("sobre escribir get en editar")

        print(request)
        
        try:
            t = request.GET["t"]
        except:
            t = None

        print(t)
        self.object = self.get_object()
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        context = self.get_context_data(object=self.object, form=form,t=t)
        print(form_class,form,context)
        return self.render_to_response(context)


@login_required(login_url="/login/")
@permission_required("fac.change_cliente",login_url="/login/")
def clienteInactivar(request,id):
    cliente = Cliente.objects.filter(pk=id).first()

    if request.method=="POST":
        if cliente:
            cliente.estado = not cliente.estado
            cliente.save()
            return HttpResponse("OK")
        return HttpResponse("FAIL")
    
    return HttpResponse("FAIL")

class FacturaView(SinPrivilegios, generic.ListView):
    model = FacturaEnc
    template_name = "fac/factura_list.html"
    context_object_name = "obj"
    permission_required="fac.view_facturaenc"

    def get_queryset(self):
        user = self.request.user
        # print(user,"usuario")
        qs = super().get_queryset()
        for q in qs:
            print(q.uc,q.id)
        
        if not user.is_superuser:
            qs = qs.filter(uc=user)

        for q in qs:
            print(q.uc,q.id)

        return qs

@login_required(login_url='/login/')
@permission_required('fac.view_facturaenc', login_url='/login/')
def facturas(request, id=None):
    template_name = 'fac/facturas.html'
    detalle = {}
    context = {}

    if request.method == "GET":
        if id:  # Edición de factura
            enc = FacturaEnc.objects.filter(pk=id).first()
            if not enc:
                messages.error(request, 'Factura no existe')
                return redirect('fac:factura_list')
            detalle = FacturaDet.objects.filter(factura=enc)
        else:  # Nueva factura
            enc = None  # No crear ni guardar aún

        clientes = Cliente.objects.filter(estado=True)
        context = {
            'enc': enc,
            'detalle': detalle,
            'clientes': clientes,
            'tipo_pago_actual': enc.tipo_pago if enc else '',
            'tipo_vencimiento_actual': enc.tipo_vencimiento if enc else '',
            'cantidad_cuotas_actual': enc.cantidad_cuotas if enc else '',
            'dias_vencimiento_irregular_actual': enc.dias_vencimiento_irregular if enc else '',
        }

    if request.method == "POST":
        enc_id = request.POST.get("enc_id")
        if enc_id:
            enc = FacturaEnc.objects.get(pk=enc_id)
        else:
            enc = FacturaEnc(total=0)

        # Obtener y asignar el cliente correctamente
        cliente_id = request.POST.get("enc_cliente")
        if cliente_id and cliente_id != "0":
            try:
                cliente = Cliente.objects.get(pk=cliente_id)
                enc.cliente = cliente
            except Cliente.DoesNotExist:
                messages.error(request, "Cliente no válido.")
                return redirect('fac:factura_edit', enc.id if enc.id else "")
        else:
            messages.error(request, "Debe seleccionar un cliente.")
            return redirect('fac:factura_edit', enc.id if enc.id else "")

        # Actualizar campos de la factura
        enc.descuento = float(request.POST.get("enc_descuento", 0) or 0)
        enc.tipo_pago = request.POST.get("tipo_pago", 'CO')
        enc.cantidad_cuotas = int(request.POST.get("cantidad_cuotas", 1) or 1)
        enc.tipo_vencimiento = request.POST.get("tipo_vencimiento", 'RE')
        enc.dias_vencimiento_irregular = request.POST.get("dias_irregulares", None)

        if enc.tipo_pago == 'CO':
            enc.cantidad_cuotas = 1
            enc.tipo_vencimiento = 'RE'
            enc.dias_vencimiento_irregular = None
            Cuenta.objects.filter(factura=enc).delete()

        if not enc.id:
            enc.uc = request.user
        else:
            enc.um = request.user.id

        enc.save()
        messages.success(request, 'Factura Guardada')
        return redirect('fac:factura_edit', enc.id)

    return render(request, template_name, context)


class ProductoView(SinPrivilegios,generic.ListView):
    model = Producto
    template_name = "fac/buscar_producto.html"
    context_object_name = "obj"
    permission_required="inv.view_producto"


@login_required(login_url='/login/')
@permission_required('fac.delete_facturadet', login_url='/login/')
def borrar_detalle_factura(request,id):
    template_name="fac/factura_borrar_detalle.html"
    det = FacturaDet.objects.get(pk=id)
    
    if request.method=="GET":
        context={'det':det}
    
    if request.method=="POST":
        # Simulación de validación de usuario y contraseña para anular
        user_input = request.POST.get("usuario")
        pass_input = request.POST.get("password")
        
        # En un sistema real, aquí se verificaría el usuario/contraseña
        # Para el ejemplo, asumimos que siempre es válido o se verifica con un usuario específico
        if user_input == request.user.username and request.user.check_password(pass_input):
            det.delete()
            return HttpResponse("OK")
        else:
            return HttpResponse("FAIL")

    return render(request,template_name,context)


@login_required(login_url="/login/")
@permission_required("fac.change_cliente",login_url="/login/")
def cliente_add_modify(request,pk=None):
    template_name="fac/cliente_form.html"
    context = {}

    if request.method=="GET":
        context["t"]="fc"
        if not pk:
            form = ClienteForm()
        else:
            cliente = Cliente.objects.filter(id=pk).first()
            form = ClienteForm(instance=cliente)
            context["obj"]=cliente
        context["form"] = form
    else: # POST
        nombres = request.POST.get("nombres")
        apellidos = request.POST.get("apellidos")
        celular = request.POST.get("celular")
        tipo = request.POST.get("tipo")
        usr = request.user

        if not pk: # Crear nuevo cliente
            cliente = Cliente.objects.create(
                nombres=nombres,
                apellidos=apellidos,
                celular = celular,
                tipo = tipo,
                uc=usr,
            )
        else: # Actualizar cliente existente
            cliente = Cliente.objects.filter(id=pk).first()
            if cliente:
                cliente.nombres=nombres
                cliente.apellidos=apellidos
                cliente.celular = celular
                cliente.tipo = tipo
                cliente.um=usr.id
                cliente.save() # Guarda solo si se encontró el cliente
            else:
                return HttpResponse("No pude encontrar el Cliente a Actualizar") # Manejo de error

        if not cliente:
            return HttpResponse("No pude Guardar/Crear Cliente")
        
        id = cliente.id
        return HttpResponse(id)
    
    return render(request,template_name,context)


# Vistas para el manejo de Cuentas (cuotas)
class CuentaView(SinPrivilegios, generic.ListView):
    model = Cuenta
    template_name = "fac/cuenta_list.html"
    context_object_name = "obj"
    permission_required="fac.view_cuenta"

    def get_queryset(self):
        queryset = super().get_queryset().select_related('factura__cliente').order_by('fecha_vencimiento')

        cliente_id = self.request.GET.get('cliente')
        fecha_inicio_str = self.request.GET.get('fecha_inicio')
        fecha_fin_str = self.request.GET.get('fecha_fin')
        estado = self.request.GET.get('estado')

        if cliente_id and cliente_id != '':
            queryset = queryset.filter(factura__cliente__id=cliente_id)
        
        if fecha_inicio_str:
            fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
            queryset = queryset.filter(fecha_vencimiento__gte=fecha_inicio)
        
        if fecha_fin_str:
            fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
            queryset = queryset.filter(fecha_vencimiento__lte=fecha_fin)
        
        if estado == 'pendiente':
            queryset = queryset.filter(cobrado=False)
        elif estado == 'cobrado':
            queryset = queryset.filter(cobrado=True)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['clientes_disponibles'] = Cliente.objects.filter(estado=True).order_by('nombres', 'apellidos')
        return context


@login_required(login_url="/login/")
@permission_required("fac.change_cuenta",login_url="/login/")
def cuenta_marcar_cobrada(request, pk):
    cuenta = Cuenta.objects.filter(pk=pk).first()
    if not cuenta:
        return HttpResponse("Cuenta no encontrada", status=404)

    if request.method == "POST":
        form = CuentaForm(request.POST, instance=cuenta)
        if form.is_valid():
            cobrado = form.cleaned_data['cobrado']
            fecha_cobro = form.cleaned_data['fecha_cobro']

            cuenta.cobrado = cobrado
            # Si se marca como cobrada, la fecha de cobro es la enviada o la actual si no se provee
            # Si se desmarca, la fecha de cobro se vacía
            if cobrado:
                cuenta.fecha_cobro = fecha_cobro if fecha_cobro else datetime.now().date()
            else:
                cuenta.fecha_cobro = None
            
            cuenta.um = request.user.id # Registrar usuario que modificó
            cuenta.save()
            return HttpResponse("OK")
        else:
            # Si el formulario no es válido, puedes devolver los errores en JSON o HTML
            return HttpResponse(f"Error en formulario: {form.errors.as_json()}", status=400)
    
    else: # GET
        form = CuentaForm(instance=cuenta)
        context = {
            'obj': cuenta,
            'form': form
        }
        return render(request, "fac/cuenta_marcar_cobrada.html", context)
    

@csrf_exempt
@login_required(login_url='/login/')
@permission_required('fac.add_facturadet', login_url='/login/')
def factura_add_detalle(request):
    if request.method == "POST":
        factura_id = request.POST.get("enc_id")
        producto_id = request.POST.get("producto_id")
        cantidad = request.POST.get("cantidad")
        precio = request.POST.get("precio")
        descuento = request.POST.get("descuento", 0)

        if not (factura_id and producto_id and cantidad and precio):
            return JsonResponse({"ok": False, "error": "Datos incompletos"})

        try:
            factura = FacturaEnc.objects.get(pk=factura_id)
            producto = Producto.objects.get(pk=producto_id)
            detalle = FacturaDet.objects.create(
                factura=factura,
                producto=producto,
                cantidad=cantidad,
                precio=precio,
                descuento=descuento
            )
            return JsonResponse({"ok": True, "detalle_id": detalle.id})
        except Exception as e:
            return JsonResponse({"ok": False, "error": str(e)})

    return JsonResponse({"ok": False, "error": "Método no permitido"})