"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('comptes.urls')),
    path('api/admin/', include('comptes.admin_urls')),
    path('api/admin/structure/', include('programme.admin_urls')),
    path('api/admin/', include('programme.programme_urls')),
    path('api/admin/ia/prompts/', include('programme.prompt_ia_urls')),
    path('api/admin/ia/', include('programme.ia_urls')),
    path('api/eleve/', include('programme.eleve_urls')),
    path('api/vendeur/', include('comptes.vendeur_urls')),
    # PUBLIC (webhook NITA, voir comptes.nita_views.NitaCallbackView) —
    # préfixe séparé de /api/eleve/, jamais protégé par IsEleveActif.
    path('api/nita/', include('comptes.nita_urls')),
]
