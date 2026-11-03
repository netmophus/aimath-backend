from rest_framework.response import Response
from rest_framework.views import APIView

from comptes.permissions import IsAdminRole

from .rapport import rapport_mensuel


class RapportBudgetIAView(APIView):
    """GET /api/admin/budget-ia/?mois=AAAA-MM : réservé au rôle admin (même permission que le reste de l'administration)."""

    permission_classes = [IsAdminRole]

    def get(self, request):
        mois = request.query_params.get("mois")
        if mois is not None and not (len(mois) == 7 and mois[4] == "-" and mois[:4].isdigit() and mois[5:].isdigit()):
            return Response({"detail": "Mois invalide (AAAA-MM)."}, status=400)
        return Response(rapport_mensuel(mois))
