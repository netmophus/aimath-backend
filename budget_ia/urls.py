from django.urls import path

from .views import RapportBudgetIAView

app_name = "budget_ia"

urlpatterns = [path("", RapportBudgetIAView.as_view(), name="rapport")]
