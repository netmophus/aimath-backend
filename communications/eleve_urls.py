from django.urls import path

from . import views

app_name = "communications_eleve"

urlpatterns = [
    path("preferences/", views.MesPreferencesView.as_view()),
]
