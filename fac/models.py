#fac/models.py

from django.db import models

#Para los signals
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum

from bases.models import ClaseModelo, ClaseModelo2
from inv.models import Producto

# agregados
from datetime import date, timedelta
import calendar # Para manejo de días en el mes


class Cliente(ClaseModelo):
    NAT='Natural'
    JUR='Jurídica'
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
    NAT='CO' # Contado
    JUR='CR' # Crédito
    TIPO_PAGO = [
        (NAT,'Contado'),
        (JUR,'Crédito')
    ]

    REG='RE' # Regular
    IRR='IR' # Irregular
    TIPO_VENCIMIENTO = [
        (REG,'Vencimiento Regular'),
        (IRR,'Vencimiento Irregular')
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    fecha = models.DateTimeField(auto_now_add=True)
    sub_total=models.FloatField(default=0)
    descuento=models.FloatField(default=0)
    total=models.FloatField(default=0)

    # Nuevos campos
    tipo_pago = models.CharField(
        max_length=2,
        choices=TIPO_PAGO,
        default='CO'
    )
    tipo_vencimiento = models.CharField(
        max_length=2,
        choices=TIPO_VENCIMIENTO,
        null=True,
        blank=True
    )
    cantidad_cuotas = models.PositiveIntegerField(
        default=1
    )
    # ... (resto de los campos existentes)

    def __str__(self):
        return '{}'.format(self.id)

    def save(self):
        self.total = self.sub_total - self.descuento
        super(FacturaEnc,self).save()

    class Meta:
        verbose_name_plural = "Encabezado Facturas"
        verbose_name="Encabezado Factura"
        permissions = [
            ('sup_caja_facturaenc','Permisos de Supervisor de Caja Encabezado')
        ]
    

class FacturaDet(ClaseModelo2):
    factura = models.ForeignKey(FacturaEnc,on_delete=models.CASCADE)
    producto=models.ForeignKey(Producto,on_delete=models.CASCADE)
    cantidad=models.BigIntegerField(default=0)
    precio=models.FloatField(default=0)
    sub_total=models.FloatField(default=0)
    descuento=models.FloatField(default=0)
    total=models.FloatField(default=0)

    def __str__(self):
        return '{}'.format(self.producto)

    def save(self):
        self.sub_total = float(float(int(self.cantidad)) * float(self.precio))
        self.total = self.sub_total - float(self.descuento)
        super(FacturaDet, self).save()
    
    class Meta:
        verbose_name_plural = "Detalles Facturas"
        verbose_name="Detalle Factura"
        permissions = [
            ('sup_caja_facturadet','Permisos de Supervisor de Caja Detalle')
        ]


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
        enc.save()

    prod=Producto.objects.filter(pk=producto_id).first()
    if prod:
        cantidad = int(prod.existencia) - int(instance.cantidad)
        prod.existencia = cantidad
        prod.save()


class Cuenta(ClaseModelo2): # ClaseModelo2 si también necesita usuario_crea, usuario_modifica
    factura = models.ForeignKey(FacturaEnc, on_delete=models.CASCADE) # O FacturaCompraEnc
    numero_cuota = models.PositiveIntegerField()
    importe = models.FloatField(default=0)
    fecha_vencimiento = models.DateField()
    pagado = models.BooleanField(default=False)
    fecha_pago = models.DateField(null=True, blank=True)

    def __str__(self):
        return 'Factura: {} - Cuota: {}'.format(self.factura, self.numero_cuota)

    class Meta:
        verbose_name_plural = "Cuentas"
        verbose_name="Cuenta"
        unique_together = ('factura', 'numero_cuota') # Para asegurar unicidad de cuota por factura



# ... (tus modelos FacturaEnc y Cuenta definidos arriba)

@receiver(post_save, sender=FacturaEnc)
def generar_cuotas_factura(sender, instance, created, **kwargs):
    if created and instance.tipo_pago == 'CR': # Solo si es una nueva factura y es a crédito
        total_factura = instance.total
        cantidad_cuotas = instance.cantidad_cuotas
        importe_por_cuota = total_factura / cantidad_cuotas
        
        fecha_factura = instance.fecha.date() # Obtener solo la fecha sin la hora

        # Eliminar cuotas existentes si la factura se actualiza a crédito desde otro tipo
        # (Aunque en este prototipo, solo se generarían en 'created')
        # Cuenta.objects.filter(factura=instance).delete()

        for i in range(1, cantidad_cuotas + 1):
            fecha_vencimiento_cuota = fecha_factura

            if instance.tipo_vencimiento == 'RE': # Vencimiento Regular (Mensual)
                # Calcular la fecha de vencimiento sumando meses
                # Considerar el día del mes para mantenerlo si es posible
                target_month = fecha_factura.month + i
                target_year = fecha_factura.year + (target_month - 1) // 12
                target_month = (target_month - 1) % 12 + 1
                
                # Asegurar que el día no exceda los días del nuevo mes
                day = min(fecha_factura.day, calendar.monthrange(target_year, target_month)[1])
                fecha_vencimiento_cuota = date(target_year, target_month, day)

            elif instance.tipo_vencimiento == 'IR': # Vencimiento Irregular (Días específicos)
                # Aquí se asume que los días de vencimiento específicos
                # vendrían de otra tabla o campo si no están en la UI directamente en el modelo
                # Para este prototipo, vamos a simularlo o asumirlo.
                # Si los días se especifican en la UI por cada cuota, se necesitaría otro modelo.
                # Para un ensayo, podemos asumir un patrón simple o que se cargan manualmente después.
                
                # Ejemplo de un patrón irregular simple (se debería ajustar según la UI)
                # Para un escenario más real, los días se guardarían en un modelo intermedio
                # o se pasarían a través de un JSONField en FacturaEnc.
                
                # Para este ensayo, asumamos un ejemplo: 30, 45, 60 días
                # En un sistema real, los días irregulares de cada cuota
                # se guardarían en una relación Many-to-Many o un campo JSON.
                
                # Para el prototipo, si no tenemos los días específicos,
                # no podemos generar un vencimiento irregular preciso aquí.
                # Esto es una limitación del prototipo de señal sin el modelo de días irregulares.
                
                # Asumamos que para este ensayo, los días para cada cuota irregular
                # se almacenan en un campo `dias_vencimiento_irregular` en `FacturaEnc`
                # como una lista de enteros (ej: [30, 45, 60]).
                # **Nota:** Esto requeriría un campo `JSONField` en `FacturaEnc`
                # y una lógica de entrada en la interfaz para llenarlo.
                
                # Para este ensayo, vamos a poner un placeholder,
                # ya que los días irregulares NO ESTÁN en el modelo FacturaEnc aún.
                # Si se implementara, sería algo así:
                # dias_irregulares = instance.dias_vencimiento_irregular # Asumiendo que es un JSONField
                # if i <= len(dias_irregulares):
                #    dias_a_sumar = dias_irregulares[i-1]
                #    fecha_vencimiento_cuota = fecha_factura + timedelta(days=dias_a_sumar)
                # else:
                #    # Manejo de error o valor por defecto si no hay suficientes días
                #    pass
                
                # Para el ENSAYO, si no tenemos el campo, hagamos un ejemplo fijo:
                # Días de vencimiento irregulares de ejemplo: 30, 45, 60
                dias_irregulares_ejemplo = [30, 45, 60] # Esto vendría de la UI real
                if i <= len(dias_irregulares_ejemplo):
                    dias_a_sumar = dias_irregulares_ejemplo[i-1]
                    fecha_vencimiento_cuota = fecha_factura + timedelta(days=dias_a_sumar)
                else:
                    # Si hay más cuotas que días definidos, usar el último día del patrón o un valor por defecto
                    fecha_vencimiento_cuota = fecha_factura + timedelta(days=dias_irregulares_ejemplo[-1])
            
            # Crear la instancia de Cuenta
            Cuenta.objects.create(
                factura=instance,
                numero_cuota=i,
                importe=importe_por_cuota,
                fecha_vencimiento=fecha_vencimiento_cuota,
                pagado=False
            )


