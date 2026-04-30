from django.contrib.auth import views as auth_views
from django.urls import path

from .views import PantryDashboardView, account_view, ajax_remove_item, otp_login_view, register_view

urlpatterns = [
    path("login/", otp_login_view, name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="smart_pantry:login"), name="logout"),
    path("register/", register_view, name="register"),
    path("account/", account_view, name="account"),
    path("ajax/remove-item/", ajax_remove_item, name="ajax_remove_item"),
    path("", PantryDashboardView.as_view(), name="dashboard"),
]
