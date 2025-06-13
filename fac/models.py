#fac/models.py

from django.db import models

#Para los signals
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum

from bases.models import ClaseModelo, ClaseModelo2
from inv.models import Producto

# Agregados para la lógica de cuotas
from datetime import date, timedelta
import calendar
import json # Para manejar JSONField o parsear string de días


class Cliente(ClaseModelo):
    NAT='NA'
    JUR='JU'
    TIPO_CLIENTE = [
        (NAT,'Natural'),
        (JUR,'Jurídica')
    ]
    nombres = models.CharField(
        max_length=100
    )
    apellidos = models.CharField(
        max_length=100
    )
    celular = models.CharField(
        max_length=20,
        null=True,
        blank=True
    )
    tipo=models.CharField(
        max_length=10,
        choices=TIPO_CLIENTE,
        default=NAT
    )

    def __str__(self):
        return '{} {}'.format(self.apellidos,self.nombres)

    def save(self, *args, **kwargs):
        self.nombres = self.nombres.upper()
        self.apellidos = self.apellidos.upper()
        super(Cliente, self).save( *args, **kwargs)

    class Meta:
        verbose_name_plural = "Clientes"


    
class FacturaEnc(ClaseModelo2):
    CO='CO' # Contado
    CR='CR' # Crédito
    TIPO_PAGO = [
        (CO,'Contado'),
        (CR,'Crédito')
    ]

    RE='RE' # Vencimiento Regular
    IR='IR' # Vencimiento Irregular
    TIPO_VENCIMIENTO = [
        (RE,'Regular'),
        (IR,'Irregular')
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    fecha = models.DateTimeField(auto_now_add=True)
    sub_total=models.FloatField(default=0)
    descuento=models.FloatField(default=0)
    total=models.FloatField(default=0)
    
    # Nuevos campos para manejar el crédito
    tipo_pago = models.CharField(
        max_length=10,
        choices=TIPO_PAGO,
        default=CO,
        help_text="Tipo de pago: Contado o Crédito"
    )
    cantidad_cuotas = models.IntegerField(
        default=1,
        help_text="Número de cuotas si es a crédito"
    )
    tipo_vencimiento = models.CharField(
        max_length=10,
        choices=TIPO_VENCIMIENTO,
        default=RE,
        help_text="Tipo de vencimiento de cuotas: Regular o Irregular"
    )
    # Campo para almacenar los días de vencimiento irregulares (ej: [30, 45, 60])
    # Se recomienda usar JSONField para esto en Django 3.1+ o Text/CharField para versiones anteriores
    dias_vencimiento_irregular = models.CharField(
        max_length=255, # Suficiente para una cadena JSON de días
        blank=True,
        null=True,
        help_text="Lista de días para vencimientos irregulares (ej: '30,60,90')"
    )


    def __str__(self):
        return 'Factura Nro. {}'.format(self.id)

    def save(self, *args, **kwargs):
        # Asegurarse que el total siempre sea >= 0
        if self.total < 0:
            self.total = 0
        super(FacturaEnc, self).save(*args, **kwargs)

    class Meta:
        verbose_name_plural = "Encabezado Facturas"
        verbose_name="Encabezado Factura"
        permissions = [
            ('sup_caja_facturaenc','Permisos de Supervisor de Caja Encabezado')
        ]
    

class FacturaDet(ClaseModelo):
    factura = models.ForeignKey(FacturaEnc, on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.IntegerField(default=0)
    precio = models.FloatField(default=0)
    sub_total=models.FloatField(default=0)
    descuento=models.FloatField(default=0)
    total=models.FloatField(default=0)
    #cuenta = models.ForeignKey(

    def __str__(self):
        return '{}'.format(self.producto)

    def save(self, *args, **kwargs):
        self.sub_total = float(float(int(self.cantidad)) * float(self.precio))
        self.total = self.sub_total - float(self.descuento)
        super(FacturaDet, self).save(*args, **kwargs)
    
    class Meta:
        verbose_name_plural = "Detalles Facturas"
        verbose_name="Detalle Factura"
        permissions = [
            ('sup_caja_facturadet','Permisos de Supervisor de Caja Detalle')
        ]


# Modelo para las cuotas generadas por las facturas a crédito
class Cuenta(ClaseModelo2):
    factura = models.ForeignKey(FacturaEnc, on_delete=models.CASCADE, related_name="cuotas")
    numero_cuota = models.IntegerField(default=1)
    importe = models.FloatField(default=0)
    fecha_vencimiento = models.DateField()
    cobrado = models.BooleanField(default=False)
    fecha_cobro = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"Cuota {self.numero_cuota} de Factura {self.factura.id}"

    class Meta:
        verbose_name_plural = "Cuentas por Cobrar/Pagar"
        verbose_name = "Cuenta"
        unique_together = ('factura', 'numero_cuota') # Cada cuota debe ser única por factura y número
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


# Signals para actualizar FacturaEnc al guardar/eliminar FacturaDet
@receiver(post_save, sender=FacturaDet)
def detalle_fac_guardar(sender,instance,**kwargs):
    factura_id = instance.factura.id
    producto_id = instance.producto.id

    enc = FacturaEnc.objects.get(pk=factura_id)
    if enc:
        sub_total = FacturaDet.objects \
            .filter(factura=factura_id) \
            .aggregate(sub_total=Sum('sub_total')) \
            .get('sub_total',0.00)
        
        descuento = FacturaDet.objects \
            .filter(factura=factura_id) \
            .aggregate(descuento=Sum('descuento')) \
            .get('descuento',0.00)
        
        enc.sub_total = sub_total
        enc.descuento = descuento
        enc.total = sub_total - descuento
        enc.save() # Guarda la factura, pero evita el signal de la factura para no crear cuotas en bucle
    
    # Actualizar existencia del producto
    prod = Producto.objects.filter(pk=producto_id).first()
    if prod:
        prod.existencia = prod.existencia - instance.cantidad
        prod.save()


@receiver(post_delete, sender=FacturaDet)
def detalle_fac_borrar(sender,instance,**kwargs):
    factura_id = instance.factura.id
    producto_id = instance.producto.id

    enc = FacturaEnc.objects.get(pk=factura_id)
    if enc:
        sub_total = FacturaDet.objects \
            .filter(factura=factura_id) \
            .aggregate(sub_total=Sum('sub_total')) \
            .get('sub_total',0.00)
        
        descuento = FacturaDet.objects \
            .filter(factura=factura_id) \
            .aggregate(descuento=Sum('descuento')) \
            .get('descuento',0.00)
        
        enc.sub_total = sub_total
        enc.descuento = descuento
        enc.total = sub_total - descuento
        enc.save() # Guarda la factura, pero evita el signal de la factura para no crear cuotas en bucle

    # Regresar existencia del producto
    prod = Producto.objects.filter(pk=producto_id).first()
    if prod:
        prod.existencia = prod.existencia + instance.cantidad
        prod.save()


@receiver(post_save, sender=FacturaEnc)
def generar_cuotas(sender, instance, created, **kwargs):
    if created and instance.tipo_pago == FacturaEnc.CR:
        # Eliminar cuotas existentes si se edita una factura y cambia a crédito
        Cuenta.objects.filter(factura=instance).delete()

        # (aunque en 'created' solo se ejecuta al crear, útil si se modifica el signal para 'changed' también)
        # instance.cuotas.all().delete() # Esto se ejecutaría si se permite editar el tipo_pago después de crear

        total_a_financiar = instance.total
        cantidad_cuotas = instance.cantidad_cuotas
        importe_por_cuota = total_a_financiar / cantidad_cuotas
        fecha_factura = instance.fecha.date() # Obtener solo la fecha

        for i in range(1, cantidad_cuotas + 1):
            fecha_vencimiento_cuota = None

            if instance.tipo_vencimiento == FacturaEnc.RE:
                # Vencimiento Regular: Cada cuota vence el mismo día del mes siguiente
                # Ejemplo: FCP-30-60-90 días (asumiendo que 30 días es 1 mes, 60 es 2 meses)
                # Esta es una interpretación común: (meses_a_sumar * 30 días)
                meses_a_sumar = i
                
                # Una forma más robusta de sumar meses es:
                # (Considerando fin de mes para evitar errores en febrero, etc.)
                year = fecha_factura.year + (fecha_factura.month + meses_a_sumar - 1) // 12
                month = (fecha_factura.month + meses_a_sumar - 1) % 12 + 1
                day = min(fecha_factura.day, calendar.monthrange(year, month)[1])
                fecha_vencimiento_cuota = date(year, month, day)

            elif instance.tipo_vencimiento == FacturaEnc.IR:
                # Vencimiento Irregular: Días específicos para cada cuota
                dias_irregulares_str = instance.dias_vencimiento_irregular
                if dias_irregulares_str:
                    try:
                        dias_irregulares = [int(d.strip()) for d in dias_irregulares_str.split(',') if d.strip()]
                        if i <= len(dias_irregulares):
                            dias_a_sumar = dias_irregulares[i-1]
                            fecha_vencimiento_cuota = fecha_factura + timedelta(days=dias_a_sumar)
                        else:
                            # Si hay más cuotas que días definidos, usar el último día del patrón
                            # o lanzar un error si es un caso no esperado.
                            # Aquí, por simplicidad, se usa el último día, o se podría repetir el patrón, etc.
                            fecha_vencimiento_cuota = fecha_factura + timedelta(days=dias_irregulares[-1])
                    except ValueError:
                        # Manejar error si el formato de días_vencimiento_irregular no es válido
                        print(f"Error: Formato de días_vencimiento_irregular incorrecto: {dias_irregulares_str}")
                        fecha_vencimiento_cuota = fecha_factura + timedelta(days=30 * i) # Fallback a regular
                else:
                    # Si es irregular pero no se especificaron días, se podría manejar como error o default
                    print("Advertencia: Tipo de vencimiento irregular sin días especificados.")
                    fecha_vencimiento_cuota = fecha_factura + timedelta(days=30 * i) # Fallback

            if fecha_vencimiento_cuota:
                Cuenta.objects.create(
                    factura=instance,
                    numero_cuota=i,
                    importe=importe_por_cuota,
                    fecha_vencimiento=fecha_vencimiento_cuota,
                    uc=instance.uc # Usuario que creó la factura
                )

