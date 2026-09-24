from django.urls import path

from .prompt_ia_views import PromptsNotionView

app_name = "programme_prompt_ia_admin"

urlpatterns = [
    path("<int:notion_id>/", PromptsNotionView.as_view(), name="prompts-notion"),
]
