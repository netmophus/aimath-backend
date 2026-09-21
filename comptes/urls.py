from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import InscriptionEleveView, MeView, TelephoneTokenObtainPairView

app_name = "comptes"

urlpatterns = [
    path("register/", InscriptionEleveView.as_view(), name="register"),
    path("login/", TelephoneTokenObtainPairView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="refresh"),
    path("me/", MeView.as_view(), name="me"),
]
