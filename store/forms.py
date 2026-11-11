from django import forms

from .models import Order, Product


class BootstrapMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"
            if isinstance(field.widget, forms.Select):
                css = "form-select"
            field.widget.attrs.setdefault("class", css)

    def _post_clean(self):
        super()._post_clean()
        for name in self.errors:
            if name in self.fields:
                w = self.fields[name].widget
                w.attrs["class"] = (w.attrs.get("class", "") + " is-invalid").strip()


class CheckoutForm(BootstrapMixin, forms.ModelForm):
    payment_method = forms.ChoiceField(choices=Order.PaymentMethod.choices, initial=Order.PaymentMethod.QR,
                                       widget=forms.RadioSelect, required=False)

    def clean_payment_method(self):
        return self.cleaned_data.get("payment_method") or Order.PaymentMethod.COD

    class Meta:
        model = Order
        fields = ["full_name", "phone", "address", "note"]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3, "placeholder": "House no., street, district, city"}),
            "phone": forms.TextInput(attrs={"placeholder": "012 345 678"}),
            "note": forms.TextInput(attrs={"placeholder": "Optional, e.g. call before delivery"}),
        }

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        digits = "".join(c for c in phone if c.isdigit())
        if len(digits) < 8:
            raise forms.ValidationError("Please enter a valid phone number (at least 8 digits).")
        return phone


class ProductForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "category", "brand", "price", "stock", "description", "specs", "image",
                  "is_featured", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4}),
                   "specs": forms.Textarea(attrs={"rows": 6, "class": "form-control font-monospace small"})}

    def save(self, commit=True):
        product = super().save(commit=False)
        if "image" in self.changed_data:
            # A new upload replaces any credited photo, so its credit no longer applies.
            product.photo_credit = product.photo_license = product.photo_source = ""
            product.photo_similar = False
        if commit:
            product.save()
        return product


class OrderStatusForm(BootstrapMixin, forms.Form):
    status = forms.ChoiceField(choices=Order.Status.choices)
