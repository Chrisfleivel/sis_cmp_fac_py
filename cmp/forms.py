#cmp/forms.py
from django import forms
from .models import Proveedor, ComprasEnc # Asegúrate de importar ComprasEnc

class ProveedorForm(forms.ModelForm):
    email = forms.EmailField(max_length=254)
    class Meta:
        model=Proveedor
        exclude = ['um','fm','uc','fc']
        widget={'descripcion': forms.TextInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in iter(self.fields):
            self.fields[field].widget.attrs.update({
                'class': 'form-control'
            })

    def clean(self):
        try:
            sc = Proveedor.objects.get(
                descripcion=self.cleaned_data["descripcion"].upper()
            )

            if not self.instance.pk:
                print("Registro ya existe")
                raise forms.ValidationError("Registro Ya Existe")
            elif self.instance.pk!=sc.pk:
                print("Cambio no permitido")
                raise forms.ValidationError("Cambio No Permitido")
        except Proveedor.DoesNotExist:
            pass
        return self.cleaned_data

class ComprasEncForm(forms.ModelForm):
    fecha_compra = forms.DateInput()
    fecha_factura = forms.DateInput()
    
    class Meta:
        model=ComprasEnc
        fields=[
            'proveedor','fecha_compra','observacion',
            'no_factura','fecha_factura','sub_total',
            'descuento','total',
            # Nuevos campos para crédito
            'tipo_pago', 'num_cuotas', 'tipo_cuota', 'dias_vencimiento_irregular'
        ]
        exclude = ['sub_total', 'descuento', 'total', 'uc', 'um']  # Excluye los campos calculados y de usuario

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in iter(self.fields):
            self.fields[field].widget.attrs.update({
                'class': 'form-control'
            })
        self.fields['fecha_compra'].widget.attrs['readonly'] = True
        self.fields['fecha_factura'].widget.attrs['readonly'] = True
        #self.fields['sub_total'].widget.attrs['readonly'] = True
        #self.fields['descuento'].widget.attrs['readonly'] = True
        #self.fields['total'].widget.attrs['readonly'] = True

        # Campos de crédito inicialmente ocultos o deshabilitados
        self.fields['num_cuotas'].widget.attrs['min'] = 1
        self.fields['num_cuotas'].widget.attrs['max'] = 36 # Ejemplo de máximo
        self.fields['num_cuotas'].required = False # Puede ser nulo si es contado
        self.fields['tipo_cuota'].required = False
        self.fields['dias_vencimiento_irregular'].required = False

        # Esto permite que el campo JSONField reciba una cadena de texto para ser parseada por el modelo
        # En la plantilla, este campo se puede mostrar como un textarea
        self.fields['dias_vencimiento_irregular'].widget.attrs.update({
            'placeholder': 'Ej: [30, 60, 90] para cuotas irregulares'
        })
        self.fields['dias_vencimiento_irregular'].help_text = 'Ingrese una lista JSON de días para cuotas irregulares (Ej: [30, 60, 90])'