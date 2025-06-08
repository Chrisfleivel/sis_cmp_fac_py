#fac/forms.py
from django import forms

from .models import Cliente, FacturaEnc, Cuenta # Importar nuevos modelos

class ClienteForm(forms.ModelForm):
    class Meta:
        model=Cliente
        fields=['nombres','apellidos','tipo',
            'celular','estado']
        exclude = ['um','fm','uc','fc']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in iter(self.fields):
            self.fields[field].widget.attrs.update({
                'class': 'form-control'
            })


class FacturaEncForm(forms.ModelForm):
    class Meta:
        model = FacturaEnc
        fields = [
            'cliente', 'tipo_pago', 'tipo_vencimiento',
            'cantidad_cuotas', 'dias_vencimiento_irregular'
        ]
        # No uses exclude aquí

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'form-control'
            })
            if field in ['tipo_vencimiento', 'cantidad_cuotas', 'dias_vencimiento_irregular']:
                self.fields[field].required = False
        self.fields['cliente'].required = True


class CuentaForm(forms.ModelForm):
    # Campo booleano para marcar como cobrado/pendiente
    cobrado = forms.BooleanField(
        required=False,
        label='Marcar como Cobrada',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    # Campo de fecha de cobro, puede ser opcional
    fecha_cobro = forms.DateField(
        required=False,
        label='Fecha de Cobro',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    class Meta:
        model = Cuenta
        fields = ['cobrado', 'fecha_cobro'] # Solo estos campos son editables
        exclude = ['factura', 'numero_cuota', 'importe', 'fecha_vencimiento', 'uc', 'fc', 'um', 'fm']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ajustar los atributos de los campos, excepto para el checkbox
        for field_name, field in self.fields.items():
            if field_name != 'cobrado':
                field.widget.attrs.update({'class': 'form-control'})
            # Si la cuota ya está cobrada, el campo cobrado debe reflejarlo
            if 'instance' in kwargs and kwargs['instance']:
                if field_name == 'cobrado':
                    field.initial = kwargs['instance'].cobrado
                if field_name == 'fecha_cobro' and kwargs['instance'].fecha_cobro:
                    field.initial = kwargs['instance'].fecha_cobro.strftime('%Y-%m-%d') # Formato para input type=date