"""
Mixin des vues IA longues. `post` décide : exécuter tout de suite (mode synchrone, ou exécution par le worker) ou
valider vite puis mettre en file et répondre 202 avec l'identifiant de la tâche.

Chaque vue fournit :
  - `executer(request, *args, **kwargs)` : l'ancien `post`, inchangé (validation + traitement), renvoie une Response ;
  - `preparer(request, *args, **kwargs)` : validation RAPIDE (404, 400, fonction activée...). Renvoie une Response
    (réponse immédiate), None (rien à mettre en file : exécuter tout de suite) ou une DemandeTache.
"""

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response

from budget_ia.http import reponse_refus
from programme.ia.exceptions import RefusBudget

from .service import DemandeTache, etat_public, mettre_en_file


class VueAsynchrone:
    def post(self, request, *args, **kwargs):
        if getattr(request, "execution_tache", False) or not settings.IA_TRAITEMENT_ASYNCHRONE:
            return self.executer(request, *args, **kwargs)
        decision = self.preparer(request, *args, **kwargs)
        if decision is None:
            return self.executer(request, *args, **kwargs)
        if not isinstance(decision, DemandeTache):
            return decision
        try:
            tache = mettre_en_file(utilisateur=request.user, vue=self, kwargs=kwargs, demande=decision)
        except RefusBudget as exc:   # trop de tâches actives : 429 propre, jamais une erreur 500
            return reponse_refus(exc)
        return Response({"tache": etat_public(tache)}, status=status.HTTP_202_ACCEPTED)
