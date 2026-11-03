from rest_framework.response import Response

from programme.ia.exceptions import RefusBudget


def reponse_refus(exc: RefusBudget) -> Response:
    """Réponse élève : message court et code stable, jamais de montant, de modèle ni de réglage."""
    return Response({"detail": exc.args[0], "code": exc.code}, status=exc.statut_http)
