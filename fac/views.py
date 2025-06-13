#fac/views.py

from django.shortcuts import render,redirect
from django.views import generic

from django.views.decorators.csrf import csrf_exempt

from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse, JsonResponse
from datetime import datetime, date, timedelta
from django.contrib import messages

from django.contrib.auth import authenticate
from django.db.models import Sum

from bases.views import SinPrivilegios

from .models import Cliente, FacturaEnc, FacturaDet, Cuenta # Importar el nuevo modelo Cuenta
from .forms import ClienteForm, CuentaForm # Asegúrate de importar CuentaForm
import inv.views as inv
from inv.models import Producto
from django.views.decorators.http import require_GET, require_POST


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
        if not enc.dias_vencimiento_irregular:
            enc.dias_vencimiento_irregular = request.POST.get("dias_vencimiento_irregular", None)
        enc.total = FacturaDet.objects.filter(factura=enc).aggregate(total=Sum('total'))['total'] or 0
        enc.save()
        actualizar_total_y_cuotas(enc, request.user)
        if enc.tipo_pago == 'CO':
            enc.cantidad_cuotas = 1
            enc.tipo_vencimiento = 'RE'
            enc.dias_vencimiento_irregular = None
            Cuenta.objects.filter(factura=enc).delete()

        if not enc.id:
            enc.uc = request.user
        else:
            enc.um = request.user
        
        enc.total = FacturaDet.objects.filter(factura=enc).aggregate(total=Sum('total'))['total'] or 0
        enc.save()
        actualizar_total_y_cuotas(enc, request.user)

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
        dias_irregulares = request.POST.get("dias_vencimiento_irregular", "")
        factura_id = request.POST.get("enc_id")
        producto_id = request.POST.get("producto_id")
        cantidad = request.POST.get("cantidad")
        precio = request.POST.get("precio")
        descuento = request.POST.get("descuento", 0)
        # Imprime los valores recibidos para depuración
        print(f"factura_id: {factura_id}, producto_id: {producto_id}, cantidad: {cantidad}, precio: {precio}, descuento: {descuento}")
        print(f"dias_irregulares: {dias_irregulares}")
        if not (factura_id and producto_id and cantidad and precio):
            missing_fields = []
            if not factura_id: missing_fields.append("factura_id")
            if not producto_id: missing_fields.append("producto_id")
            if not cantidad: missing_fields.append("cantidad")
            if not precio: missing_fields.append("precio")
            return JsonResponse({"ok": False, "error": f"Datos incompletos: {', '.join(missing_fields)}"})

        try:
            factura_id = int(factura_id)
            producto_id = int(producto_id)
            cantidad = int(cantidad) # O int si no permites decimales
            precio = float(precio)     # O Decimal si usas DecimalField en el modelo
            descuento = float(descuento)

            factura = FacturaEnc.objects.get(pk=factura_id)
            if dias_irregulares:
                factura.dias_vencimiento_irregular = dias_irregulares
                factura.save()
            else:
                print(f"Factura {factura.id} si tiene días de vencimiento irregulares definidos, no se actualizarán las cuotas.")  
            producto = Producto.objects.get(pk=producto_id)
            detalle = FacturaDet.objects.create(
                factura=factura,
                producto=producto,
                cantidad=cantidad,
                precio=precio,
                descuento=descuento,
                uc=request.user,  # Usuario que crea el detalle
            )
            # AHORA recalcula el total y las cuotas
            factura.total = FacturaDet.objects.filter(factura=factura).aggregate(total=Sum('total'))['total'] or 0
            factura.save()
            if factura.tipo_vencimiento == 'RE' or factura.dias_vencimiento_irregular:
                actualizar_total_y_cuotas(factura, request.user)

            return JsonResponse({"ok": True, "detalle_id": detalle.id})
        except FacturaEnc.DoesNotExist:
            return JsonResponse({"ok": False, "error": f"Error: Factura con ID '{factura_id}' no encontrada."})
        except Producto.DoesNotExist:
            return JsonResponse({"ok": False, "error": f"Error: Producto con ID '{producto_id}' no encontrado."})
        except ValueError as ve:
            return JsonResponse({"ok": False, "error": f"Error en el tipo de datos (cantidad/precio/descuento): {ve}. Asegúrese de que son números válidos."})
        except Exception as e:
            # Captura cualquier otro error inesperado y devuelve un mensaje útil
            print(f"Error al agregar detalle: {e}")  # Para depuración
            return JsonResponse({"ok": False, "error": f"Error interno del servidor al agregar detalle: {e}"})
    return JsonResponse({"ok": False, "error": "Método no permitido"}, status=405)



@login_required(login_url='/login/')
def buscar_producto_modal(request):
    productos = Producto.objects.filter(estado=True) # Filtra por activos o .all()
    return render(request, 'fac/buscar_producto.html', {'obj': productos})



@require_GET
@login_required(login_url='/login/')
def buscar_producto_ajax(request):
    codigo = request.GET.get('codigo')
    if codigo:
        producto = Producto.objects.filter(codigo=codigo, estado=True).first()
        if producto:
            return JsonResponse({
                "ok": True,
                "id": producto.id,
                "producto": {
                    "codigo": producto.codigo,
                    "descripcion": producto.descripcion,
                    "precio": producto.precio
                }
            })
        else:
            return JsonResponse({"ok": False, "error": "Producto no encontrado"})
    # Si no hay código, devolver todos los productos (para el modal)
    productos = Producto.objects.filter(estado=True)
    return JsonResponse({
        "ok": True,
        "productos": [
            {
                "id": p.id,
                "codigo": p.codigo,
                "descripcion": p.descripcion,
                "precio": p.precio
            } for p in productos
        ]
    })



@require_GET
@login_required(login_url='/login/')
def factura_detalles(request):
    enc_id = request.GET.get("enc_id")
    if not enc_id:
        return JsonResponse({"ok": False, "error": "No se proporcionó el ID de la factura."})

    try:
        detalles = FacturaDet.objects.filter(factura_id=enc_id)
        lista = []
        for det in detalles:
            lista.append({
                "id": det.id,
                "codigo": det.producto.codigo if det.producto else "",
                "descripcion": det.producto.descripcion if det.producto else "",
                "cantidad": det.cantidad,
                "precio": float(det.precio),
                "descuento": float(det.descuento),
                "sub_total": float(det.sub_total) if hasattr(det, "sub_total") else float(det.cantidad) * float(det.precio),
                "total": float(det.total) if hasattr(det, "total") else float(det.cantidad) * float(det.precio) - float(det.descuento),
            })
        return JsonResponse({"ok": True, "detalles": lista})
    except Exception as e:
        return JsonResponse({"ok": False, "error": f"Error al obtener detalles: {e}"})
    


from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from .models import FacturaDet, FacturaEnc
from django.db.models import Sum

@csrf_exempt
def borrar_detalle_ajax(request):
    if request.method == "POST":
        detalle_id = request.POST.get("id")
        try:
            detalle = FacturaDet.objects.get(pk=detalle_id)
            factura = detalle.factura
            detalle.delete()
            # Actualizar total de la factura
            factura.total = FacturaDet.objects.filter(factura=factura).aggregate(total=Sum('total'))['total'] or 0
            factura.save()
            # Recalcular cuotas si corresponde
            if factura.tipo_vencimiento == 'RE' or factura.dias_vencimiento_irregular:
                from .views import actualizar_total_y_cuotas
                actualizar_total_y_cuotas(factura, request.user)
            return JsonResponse({"ok": True})
        except FacturaDet.DoesNotExist:
            return JsonResponse({"ok": False, "error": "Detalle no encontrado."})
        except Exception as e:
            return JsonResponse({"ok": False, "error": str(e)})
    return JsonResponse({"ok": False, "error": "Método no permitido."})


def recalcular_cuotas(enc, user):
    from datetime import date, timedelta
    Cuenta.objects.filter(factura=enc).delete()
    print(f"Recalculando cuotas para la factura {enc.id} con tipo de pago {enc.tipo_pago} y total {enc.total}")
    if enc.tipo_pago == 'CR' and enc.total > 0:

        cantidad_cuotas = enc.cantidad_cuotas or 1
        importe_cuota = enc.total / cantidad_cuotas
        fecha_base = date.today()
        if enc.tipo_vencimiento in ('RE','REG'):
            print(f"Tipo de vencimiento regular: {enc.tipo_vencimiento}")
            for i in range(cantidad_cuotas):
                print(f"Creando cuota {i+1} con importe {importe_cuota} y fecha de vencimiento {fecha_base + timedelta(days=30*(i+1))}")    
                fecha_vencimiento = fecha_base + timedelta(days=30*(i+1))
                Cuenta.objects.create(
                    factura=enc,
                    numero_cuota=i+1,
                    importe=importe_cuota,
                    fecha_vencimiento=fecha_vencimiento,
                    cobrado=False,
                    uc=user
                )
        elif enc.tipo_vencimiento in ('IR','IRR'):
            print(f"Tipo de vencimiento irregular: {enc.tipo_vencimiento}")
            dias_str = enc.dias_vencimiento_irregular or ''
            print(f"Días de vencimiento irregulares 2: {dias_str}")
            dias_list = [int(d.strip()) for d in dias_str.split(',') if d.strip().isdigit()]
            print(f"Días de vencimiento irregulares: {dias_list}")
            for i, dias in enumerate(dias_list):
                print(f"Creando cuota {i+1} con importe {importe_cuota} y fecha de vencimiento {fecha_base + timedelta(days=int(dias))}")   
                fecha_vencimiento = fecha_base + timedelta(days=int(dias))
                Cuenta.objects.create(
                    factura=enc,
                    numero_cuota=i+1,
                    importe=importe_cuota,
                    fecha_vencimiento=fecha_vencimiento,
                    cobrado=False,
                    uc=user
                )
        else:
            print(f"Tipo de pago no reconocido: {enc.tipo_pago}. No se crean cuotas.")



def actualizar_total_y_cuotas(factura, user):
    factura.total = FacturaDet.objects.filter(factura=factura).aggregate(total=Sum('total'))['total'] or 0
    factura.save()
    recalcular_cuotas(factura, user)

