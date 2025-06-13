#cmp/models.py
from django.db import models

#Para los signals
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum

from bases.models import ClaseModelo, ClaseModelo2 # Asegúrate de que ClaseModelo y ClaseModelo2 estén bien definidas
from inv.models import Producto
from decimal import Decimal

# Agregados para créditos
from django.utils import timezone
from datetime import date, timedelta
import calendar # Para manejo de días en el mes
from django.contrib.auth import get_user_model # Para referenciar al modelo de usuario

User = get_user_model() # Obtiene el modelo de usuario activo


class Proveedor(ClaseModelo):
    descripcion=models.CharField(
        max_length=100,
        unique=True
        )
    direccion=models.CharField(
        max_length=250,
        null=True, blank=True
        )
    contacto=models.CharField(
        max_length=100
    )
    telefono=models.CharField(
        max_length=10,
        null=True, blank=True
    )
    email=models.CharField(
        max_length=250,
        null=True, blank=True
    )

    def __str__(self):
        return '{}'.format(self.descripcion)

    def save(self, *args, **kwargs):
        self.descripcion = self.descripcion.upper()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name_plural = "Proveedores"


class ComprasEnc(ClaseModelo):
    CONTADO = 'CO'
    CREDITO = 'CR'
    TIPO_PAGO_CHOICES = [
        (CONTADO, 'Contado'),
        (CREDITO, 'Crédito'),
    ]

    REGULAR = 'R'
    IRREGULAR = 'I'
    TIPO_CUOTA_CHOICES = [
        (REGULAR, 'Regular'),
        (IRREGULAR, 'Irregular'),
    ]

    proveedor=models.ForeignKey(Proveedor,on_delete=models.CASCADE)
    
    fecha_compra=models.DateField(null=True,blank=True)
    observacion=models.TextField(blank=True,null=True)
    no_factura=models.CharField(max_length=100)
    fecha_factura=models.DateField()
    sub_total = models.DecimalField(default=0, max_digits=18, decimal_places=2, blank=True)
    descuento = models.DecimalField(default=0, max_digits=18, decimal_places=2, blank=True)
    total = models.DecimalField(default=0, max_digits=18, decimal_places=2, blank=True)

    # Campos para Compras a Crédito
    tipo_pago = models.CharField(
        max_length=2,
        choices=TIPO_PAGO_CHOICES,
        default=CONTADO,
        verbose_name='Tipo de Pago'
    )
    num_cuotas = models.IntegerField(
        default=1,
        verbose_name='Número de Cuotas'
    )
    tipo_cuota = models.CharField(
        max_length=1,
        choices=TIPO_CUOTA_CHOICES,
        default=REGULAR,
        verbose_name='Tipo de Cuota'
    )
    # Almacena días de vencimiento irregulares como JSON. Ejemplo: [30, 60, 90]
    # ...existing code...
    dias_vencimiento_irregular = models.TextField(
        blank=True,
        null=True,
        help_text="Lista de días para vencimientos irregulares (ej: '30,60,90')"
    )
    # ...existing code...

    def __str__(self):
        return '{}'.format(self.observacion)

    def save(self, *args, **kwargs):
        sub_total = self.comprasdet_set.aggregate(Sum('sub_total'))['sub_total__sum']
        descuento = self.comprasdet_set.aggregate(Sum('descuento'))['descuento__sum']
        self.sub_total = Decimal(str(sub_total)) if sub_total not in [None, ''] else Decimal('0.00')
        self.descuento = Decimal(str(descuento)) if descuento not in [None, ''] else Decimal('0.00')
        self.total = self.sub_total - self.descuento
        super(ComprasEnc, self).save(*args, **kwargs)
    
    class Meta:
        verbose_name_plural = "Encabezado Compras"
        verbose_name="Encabezado Compra"


class ComprasDet(ClaseModelo):
    compra = models.ForeignKey(ComprasEnc, on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.BigIntegerField(default=0)
    precio_prv = models.DecimalField(default=0, max_digits=18, decimal_places=2)
    sub_total = models.DecimalField(default=0, max_digits=18, decimal_places=2)
    descuento = models.DecimalField(default=0, max_digits=18, decimal_places=2)
    total = models.DecimalField(default=0, max_digits=18, decimal_places=2)
    costo = models.DecimalField(default=0, max_digits=18, decimal_places=2)

    def __str__(self):
        return '{}'.format(self.producto)

    def save(self, *args, **kwargs):
        cantidad = Decimal(self.cantidad or 0)
        precio = Decimal(self.precio_prv or 0)
        descuento = Decimal(self.descuento or 0)
        self.sub_total = cantidad * precio
        self.total = self.sub_total - descuento
        super(ComprasDet, self).save(*args, **kwargs)

    class Meta:
        verbose_name_plural = "Detalles Compras"
        verbose_name = "Detalle Compra"


class CuentaPagar(ClaseModelo): # Hereda de ClaseModelo para campos de auditoría
    compra = models.ForeignKey(ComprasEnc, on_delete=models.CASCADE, related_name='cuentas_a_pagar')
    numero_cuota = models.IntegerField(verbose_name='Número de Cuota')
    importe = models.FloatField(default=0, verbose_name='Importe de Cuota')
    fecha_vencimiento = models.DateField(verbose_name='Fecha de Vencimiento')
    fecha_pago = models.DateField(null=True, blank=True, verbose_name='Fecha de Pago')
    pagado = models.BooleanField(default=False, verbose_name='Pagado')

    def __str__(self):
        return f"Compra {self.compra.id} - Cuota {self.numero_cuota} ({'Pagada' if self.pagado else 'Pendiente'})"

    class Meta:
        verbose_name_plural = "Cuentas por Pagar"
        verbose_name = "Cuenta por Pagar"
        unique_together = ('compra', 'numero_cuota') # Asegura que no haya cuotas duplicadas para la misma compra

    def save(self, *args, **kwargs):
        # ...tu lógica personalizada...
        super().save(*args, **kwargs)


# Signals para actualizar la existencia de productos y los totales de compra
@receiver(post_delete, sender=ComprasDet)
def detalle_compra_borrar(sender,instance, **kwargs):
    id_producto = instance.producto.id
    id_compra = instance.compra.id

    enc = ComprasEnc.objects.filter(pk=id_compra).first()
    if enc:
        # Recalcular sub_total y descuento basados en los detalles restantes
        sub_total = ComprasDet.objects.filter(compra=id_compra).aggregate(sum_sub_total=Sum('sub_total')).get('sum_sub_total', 0.00)
        descuento = ComprasDet.objects.filter(compra=id_compra).aggregate(sum_descuento=Sum('descuento')).get('sum_descuento', 0.00)
        enc.sub_total = sub_total
        enc.descuento = descuento
        enc.save() # Esto volverá a calcular el total automáticamente en el método save de ComprasEnc

    prod=Producto.objects.filter(pk=id_producto).first()
    if prod:
        cantidad = int(prod.existencia) - int(instance.cantidad)
        prod.existencia = cantidad
        prod.save()



@receiver(post_save, sender=ComprasDet)
def detalle_compra_guardar(sender,instance,**kwargs):
    id_producto = instance.producto.id
    id_compra = instance.compra.id

    # Actualizar existencia del producto
    prod = Producto.objects.filter(pk=id_producto).first()
    if prod:
        if kwargs['created']: # Si es una nueva línea de detalle
            cantidad_anterior = 0
        else: # Si se está actualizando una línea de detalle existente
            # Si el producto o la cantidad se modificó, necesitamos ajustar la existencia
            try:
                original_instance = ComprasDet.objects.get(pk=instance.pk)
                cantidad_anterior = original_instance.cantidad
                if original_instance.producto.id != instance.producto.id:
                    # Si el producto cambió, restaurar la existencia del producto anterior
                    old_prod = Producto.objects.get(pk=original_instance.producto.id)
                    old_prod.existencia -= cantidad_anterior
                    old_prod.save()
            except ComprasDet.DoesNotExist:
                cantidad_anterior = 0 # No se encontró la instancia original, tratar como nueva
        
        # Ajustar la existencia del producto actual
        prod.existencia = int(prod.existencia) - cantidad_anterior + int(instance.cantidad)
        prod.save()

    # Actualizar totales en ComprasEnc
    enc = ComprasEnc.objects.filter(pk=id_compra).first()
    if enc:
        # Recalcular sub_total y descuento basados en todos los detalles
        sub_total = ComprasDet.objects.filter(compra=id_compra).aggregate(sum_sub_total=Sum('sub_total')).get('sum_sub_total', 0.00)
        descuento = ComprasDet.objects.filter(compra=id_compra).aggregate(sum_descuento=Sum('descuento')).get('sum_descuento', 0.00)
        enc.sub_total = sub_total
        enc.descuento = descuento
        enc.save() # Esto volverá a calcular el total automáticamente en el método save de ComprasEnc


@receiver(post_save, sender=ComprasEnc)
def crear_cuotas_compras(sender, instance, created, **kwargs):
    # Si es crédito, borra y regenera cuotas
    if instance.tipo_pago == ComprasEnc.CREDITO:
        # Eliminar cuotas existentes si se edita una factura de crédito a contado y viceversa (poco probable con 'created')
        # Pero si se convierte de Contado a Crédito después de guardar, esto no se activaría.
        # Para ello, se necesitaría un enfoque diferente (ej. un pre_save o un botón en la UI).
        # Aquí, asumimos que las cuotas se generan solo al crear una compra a crédito.
        
        # Borrar cuotas antiguas si existen (útil si se cambia de tipo_pago después de crear)
        # Aunque este signal es `created`, se puede añadir una lógica para `not created`
        # si se planea permitir el cambio de tipo de pago en una compra existente.
        # Por simplicidad para 'created', solo se generan.
        
        # Limpiar cuotas existentes para esta compra antes de crear nuevas (en caso de re-guardar o editar tipo_pago)
        CuentaPagar.objects.filter(compra=instance).delete()

        importe_total = instance.total
        num_cuotas = instance.num_cuotas
        fecha_factura = instance.fecha_factura

        if num_cuotas and num_cuotas > 0:
            importe_por_cuota = importe_total / num_cuotas
            
            if instance.tipo_cuota == ComprasEnc.REGULAR:
                # Vencimiento regular: cuotas cada 30 días
                for i in range(1, num_cuotas + 1):
                    fecha_vencimiento = fecha_factura + timedelta(days=30 * i)
                    CuentaPagar.objects.create(
                        compra=instance,
                        numero_cuota=i,
                        importe=importe_por_cuota,
                        fecha_vencimiento=fecha_vencimiento,
                        pagado=False,
                        uc=instance.uc
                    )
            elif instance.tipo_cuota == ComprasEnc.IRREGULAR:
                try:
                    dias_irregulares = instance.dias_vencimiento_irregular  
                    if not isinstance(dias_irregulares, list):
                        # Intentar parsear si no es una lista (podría venir como string JSON)
                        import json
                        dias_irregulares = json.loads(dias_irregulares)
                except (TypeError, ValueError, json.JSONDecodeError):
                    dias_irregulares = [] # Si hay error, tratar como lista vacía

                for i, dias_cuota in enumerate(dias_irregulares, start=1):
                    fecha_vencimiento = fecha_factura + timedelta(days=dias_cuota)
                    CuentaPagar.objects.create(
                        compra=instance,
                        numero_cuota=i,
                        importe=importe_por_cuota,
                        fecha_vencimiento=fecha_vencimiento,
                        pagado=False,
                        uc=instance.uc
                    )
    if instance.tipo_pago == ComprasEnc.CONTADO:
        CuentaPagar.objects.filter(compra=instance).delete()
        return
