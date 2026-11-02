from django import forms


class DateRangeForm(forms.Form):
    fecha_inicio = forms.DateField(
        label="Fecha de inicio",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    fecha_fin = forms.DateField(
        label="Fecha de fin",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("fecha_inicio")
        end = cleaned_data.get("fecha_fin")
        if start and end and start > end:
            raise forms.ValidationError(
                "La fecha de inicio no puede ser posterior a la fecha de fin."
            )
        return cleaned_data
