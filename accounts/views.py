from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from store.models import Product

from .demo import public_demo_accounts
from .forms import LoginForm, RegisterForm


def showcase_products():
    """A few product pictures for the side panel of the login / sign-up pages."""
    return (Product.objects.filter(is_active=True, is_featured=True)
            .exclude(image="").exclude(image__isnull=True)[:3])


def register(request):
    if request.user.is_authenticated:
        return redirect("store:home")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f"Welcome to TechCart, {user.first_name or user.username}!")
        return redirect("store:home")
    return render(request, "accounts/register.html", {"form": form, "showcase": showcase_products()})


class TechCartLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["demo_accounts"] = public_demo_accounts() if settings.SHOW_DEMO_ACCOUNTS else []
        ctx["showcase"] = showcase_products()
        return ctx

    def form_valid(self, form):
        user = form.get_user()
        messages.success(self.request, f"Welcome back, {user.first_name or user.username}!")
        return super().form_valid(form)
