from django import forms

from .models import Narxnoma


class StyledMixin:
    """Barcha maydonlarga dizayn klasslarini qo'shadi."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            w = f.widget
            if isinstance(w, forms.CheckboxInput):
                w.attrs.setdefault("class", "check")
            else:
                w.attrs.setdefault("class", "input")
                w.attrs.setdefault("placeholder", "yozing")


class NarxnomaForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = Narxnoma
        fields = ["tartib", "parametr", "tahlil_usuli", "sinov_obyekti", "narx", "har_namunaga", "aktiv"]
        widgets = {"parametr": forms.Textarea(attrs={"rows": 3})}
