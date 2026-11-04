from django.urls import path

from . import views

app_name = "communications_admin"

urlpatterns = [
    path("parametres/", views.ParametresView.as_view()),
    path("modeles/", views.ModelesView.as_view()),
    path("campagnes/apercu/", views.ApercuView.as_view()),
    path("campagnes/", views.CampagnesView.as_view()),
    path("campagnes/<int:id>/", views.CampagneDetailView.as_view()),
    path("campagnes/<int:id>/confirmer/", views.ConfirmerView.as_view()),
    path("campagnes/<int:id>/arreter/", views.ArreterView.as_view()),
    path("campagnes/<int:id>/relancer-echecs/", views.RelancerView.as_view()),
    path("messages/", views.MessagesView.as_view()),
    path("statut-activation/", views.StatutActivationView.as_view()),
    path("utilisateurs/<int:id>/preferences/", views.PreferenceView.as_view()),
    path("utilisateurs/<int:id>/consentement-parental/", views.ConsentementParentalView.as_view()),
    path("consentements-parentaux/", views.ConsentementsParentauxView.as_view()),
]
