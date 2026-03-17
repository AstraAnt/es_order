from django.urls import path
from . import views

app_name = "users"

urlpatterns = [
    path("login/", views.UserLoginView.as_view(), name="login"),
    path("logout/", views.logout_user, name="logout"),
    path("post-login/", views.post_login_redirect_view, name="post_login"),
    path("select-business-unit/", views.select_business_unit_view, name="select_business_unit"),
]