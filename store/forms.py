import json

from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password

from .models import Category, Order, Product


class BootstrapMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"
            if isinstance(field.widget, forms.Select):
                css = "form-select"
            if isinstance(field.widget, (forms.RadioSelect, forms.CheckboxSelectMultiple)):
                css = "form-check-input"
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


def parse_spec_lines(text):
    """"Processor: Intel Core i5\nMemory: 16GB" -> {"Processor": "Intel Core i5", "Memory": "16GB"}."""
    specs, bad = {}, []
    for n, line in enumerate((text or "").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        key, sep, value = line.partition(":")
        if not sep or not key.strip() or not value.strip():
            bad.append(n)
            continue
        specs[key.strip()] = value.strip()
    return specs, bad


def shrink_image(upload, max_side=1600):
    """Resize big photos so they load fast and fit in the database; keeps PNG transparency."""
    from io import BytesIO

    from django.core.files.uploadedfile import InMemoryUploadedFile
    from PIL import Image, ImageOps

    upload.seek(0)
    img = Image.open(upload)
    fmt = img.format  # exif_transpose returns a copy without it
    img = ImageOps.exif_transpose(img)
    keep_png = fmt == "PNG" or img.mode in ("RGBA", "LA", "P")
    if max(img.size) <= max_side and fmt in ("JPEG", "PNG", "WEBP"):
        upload.seek(0)
        return upload
    img.thumbnail((max_side, max_side))
    out = BytesIO()
    if keep_png:
        img.save(out, "PNG", optimize=True)
        ext, ctype = "png", "image/png"
    else:
        img.convert("RGB").save(out, "JPEG", quality=85, optimize=True)
        ext, ctype = "jpg", "image/jpeg"
    stem = upload.name.rsplit(".", 1)[0]
    return InMemoryUploadedFile(out, "image", f"{stem}.{ext}", ctype, out.tell(), None)


class ProductForm(BootstrapMixin, forms.ModelForm):
    summary = forms.CharField(
        required=False, max_length=160, label="Short summary",
        help_text="One line shown on product cards, e.g. “Core i5 · 16GB · 512GB SSD · 15.6\" FHD”.")
    spec_lines = forms.CharField(
        required=False, label="Spec sheet",
        widget=forms.Textarea(attrs={"rows": 7, "placeholder": "Processor: Intel Core i5-1335U\nMemory: 16GB DDR4\n"
                                                               "Storage: 512GB NVMe SSD\nDisplay: 15.6\" FHD 144Hz\n"
                                                               "Warranty: 2 years"}),
        help_text="One spec per line as “Name: value”. Shown as the spec table on the product page.")
    compat_json = forms.CharField(
        required=False, label="PC builder data (advanced)",
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control font-monospace small",
                                     "placeholder": '{"socket": "AM5", "memory_type": "DDR5", "tdp": 65}'}),
        help_text="Only for PC parts. JSON with socket, memory_type, form_factor, form_factors, tdp, wattage, "
                  "integrated_graphics.")

    class Meta:
        model = Product
        fields = ["name", "category", "brand", "sku", "price", "compare_at_price", "stock", "description",
                  "image", "is_featured", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4}),
                   "image": forms.ClearableFileInput(attrs={"accept": "image/*"})}
        labels = {"is_featured": "Feature on the home page", "is_active": "Visible in the store"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        specs = dict(self.instance.specs or {}) if self.instance.pk else {}
        if not self.is_bound:
            self.initial["summary"] = specs.get("summary", "")
            self.initial["spec_lines"] = "\n".join(f"{k}: {v}" for k, v in specs.items()
                                                   if k not in ("summary", "compat"))
            if specs.get("compat"):
                self.initial["compat_json"] = json.dumps(specs["compat"], ensure_ascii=False)
        self.fields["price"].widget.attrs.update({"step": "0.01", "min": "0.01"})
        self.fields["compare_at_price"].widget.attrs.update({"step": "0.01", "min": "0.01"})

    def clean_sku(self):
        sku = self.cleaned_data.get("sku", "").strip().upper()
        if sku and Product.objects.filter(sku__iexact=sku).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Another product already uses this SKU.")
        return sku

    def clean_spec_lines(self):
        specs, bad = parse_spec_lines(self.cleaned_data.get("spec_lines"))
        if bad:
            raise forms.ValidationError(f"Line {', '.join(map(str, bad))}: write each spec as “Name: value”.")
        return specs

    def clean_compat_json(self):
        text = (self.cleaned_data.get("compat_json") or "").strip()
        if not text:
            return {}
        try:
            data = json.loads(text)
        except ValueError:
            raise forms.ValidationError("This must be valid JSON, e.g. {\"socket\": \"AM5\"}.")
        if not isinstance(data, dict):
            raise forms.ValidationError("This must be a JSON object: { ... }.")
        return data

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if image and hasattr(image, "content_type"):  # a new upload
            limit = settings.MAX_UPLOAD_IMAGE_MB
            if image.size > limit * 1024 * 1024:
                raise forms.ValidationError(f"The photo is too big. Please use one under {limit} MB.")
            return shrink_image(image)
        return image

    def clean(self):
        data = super().clean()
        price, original = data.get("price"), data.get("compare_at_price")
        if price and original and original <= price:
            self.add_error("compare_at_price", "The original price must be higher than the selling price "
                                               "(or leave it empty).")
        return data

    def save(self, commit=True):
        product = super().save(commit=False)
        specs = {}
        if self.cleaned_data.get("summary"):
            specs["summary"] = self.cleaned_data["summary"]
        specs.update(self.cleaned_data.get("spec_lines") or {})
        if self.cleaned_data.get("compat_json"):
            specs["compat"] = self.cleaned_data["compat_json"]
        product.specs = specs
        if "image" in self.changed_data:
            # A new upload replaces any credited photo, so its credit no longer applies.
            product.photo_credit = product.photo_license = product.photo_source = ""
            product.photo_similar = False
        if commit:
            product.save()
        return product


class CategoryForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "group", "icon", "position"]
        help_texts = {"icon": "A Bootstrap Icons name, e.g. laptop, display, cpu, keyboard, mouse, headphones."}


class StaffRoleMixin:
    ROLE_CHOICES = [("staff", "Staff — products, orders, customers"),
                    ("owner", "Owner — everything, including managing admins")]


class AdminCreateForm(BootstrapMixin, StaffRoleMixin, forms.ModelForm):
    role = forms.ChoiceField(choices=StaffRoleMixin.ROLE_CHOICES, initial="staff", widget=forms.RadioSelect)
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    password2 = forms.CharField(label="Confirm password",
                                widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    class Meta:
        model = User
        fields = ["first_name", "last_name", "username", "email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("first_name", "email"):
            self.fields[name].required = True
        self.fields["role"].widget.attrs["class"] = "form-check-input"

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        data = super().clean()
        p1, p2 = data.get("password1"), data.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "The two passwords don't match.")
        elif p1:
            user = User(username=data.get("username", ""), email=data.get("email", ""),
                        first_name=data.get("first_name", ""))
            try:
                validate_password(p1, user)
            except forms.ValidationError as e:
                self.add_error("password1", e)
        return data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        user.is_staff = True
        user.is_superuser = self.cleaned_data["role"] == "owner"
        if commit:
            user.save()
        return user


class AdminEditForm(BootstrapMixin, StaffRoleMixin, forms.ModelForm):
    role = forms.ChoiceField(choices=StaffRoleMixin.ROLE_CHOICES, widget=forms.RadioSelect)
    new_password = forms.CharField(
        required=False, label="New password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Leave empty to keep the current password.")

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "is_active"]
        labels = {"is_active": "Account active (can log in)"}

    def __init__(self, *args, editor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.editor = editor
        self.fields["role"].initial = "owner" if self.instance.is_superuser else "staff"
        self.fields["role"].widget.attrs["class"] = "form-check-input"
        self.fields["email"].required = True
        if editor and editor.pk == self.instance.pk:
            # Nobody can lock themselves out by mistake.
            self.fields["role"].disabled = True
            self.fields["is_active"].disabled = True

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        data = super().clean()
        removing_owner = self.instance.is_superuser and (data.get("role") == "staff" or not data.get("is_active"))
        if removing_owner and not User.objects.filter(is_superuser=True, is_active=True).exclude(
                pk=self.instance.pk).exists():
            raise forms.ValidationError("The store needs at least one active owner.")
        if data.get("new_password"):
            try:
                validate_password(data["new_password"], self.instance)
            except forms.ValidationError as e:
                self.add_error("new_password", e)
        return data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_superuser = self.cleaned_data["role"] == "owner"
        if self.cleaned_data.get("new_password"):
            user.set_password(self.cleaned_data["new_password"])
        if commit:
            user.save()
        return user


class OrderStatusForm(BootstrapMixin, forms.Form):
    status = forms.ChoiceField(choices=Order.Status.choices)
