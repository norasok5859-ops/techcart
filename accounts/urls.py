from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("login/", views.TechCartLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
]
