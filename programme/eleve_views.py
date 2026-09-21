"""
Endpoints "espace élève" — lecture seule, réservés IsEleveActif (JWT +
role==eleve + statut==actif).

Règle de sécurité absolue de tout ce fichier : la classe (niveau + série) de
l'élève vient TOUJOURS de request.user, jamais d'un paramètre client. Chaque
vue qui prend un id restreint son queryset à CE périmètre AVANT de chercher
l'objet — un id d'une autre classe, ou une leçon non publiée, tombe donc dans
le 404 générique de get_object(), sans jamais confirmer qu'il existe ailleurs
(pas de distinction 403 "existe mais interdit" / 404 "n'existe pas").

GET /api/eleve/mon-programme/     → programmes de SA classe (liste plate)
GET /api/eleve/programmes/{id}/   → arbre d'UN de ses programmes, filtré
GET /api/eleve/lecons/{id}/       → contenu complet d'UNE leçon publiée de SA classe
GET /api/eleve/mes-lecons/        → (optionnel) liste plate des leçons publiées de SA classe
GET /api/eleve/glossaire/{slug}/  → un terme du glossaire (public pour tout élève actif)
GET /api/eleve/glossaire/?slugs=  → plusieurs termes en un appel (?slugs=a,b,c)

Le glossaire fait exception à la règle de cloisonnement par classe ci-dessus
pour son CONTENU (définition/exemple, voir TermeGlossaireEleveSerializer) —
seul le lien vers une leçon reste soumis à cette règle.
"""

from django.db.models import Count, Q
from rest_framework.generics import ListAPIView, RetrieveAPIView

from comptes.permissions import IsEleveActif

from .eleve_serializers import (
    LeconEleveSerializer,
    LeconListeEleveSerializer,
    ProgrammeDetailEleveSerializer,
    ProgrammeEleveSerializer,
    TermeGlossaireEleveSerializer,
)
from .models import Lecon, Programme, TermeGlossaire

_LECON_LIEE_SELECT_RELATED = (
    "lecon_liee",
    "lecon_liee__notion",
    "lecon_liee__notion__chapitre",
    "lecon_liee__notion__chapitre__theme",
    "lecon_liee__notion__chapitre__theme__programme",
)


def _programmes_de_la_classe(user):
    """Programme(s) dont niveau+série correspondent EXACTEMENT à ceux de
    l'utilisateur — `serie_id=None` matche bien "sans série" (premier cycle)."""
    return Programme.objects.filter(niveau_id=user.niveau_id, serie_id=user.serie_id)


class MonProgrammeView(ListAPIView):
    """GET /api/eleve/mon-programme/ — pas de pagination : la liste des
    matières d'une classe est toujours courte, une page suffit."""

    permission_classes = [IsEleveActif]
    serializer_class = ProgrammeEleveSerializer
    pagination_class = None

    def get_queryset(self):
        return (
            _programmes_de_la_classe(self.request.user)
            .select_related("matiere", "niveau", "serie")
            .annotate(
                nb_lecons_publiees=Count(
                    "themes__chapitres__notions__lecon",
                    filter=Q(themes__chapitres__notions__lecon__statut=Lecon.Statut.PUBLIE),
                    distinct=True,
                )
            )
            .order_by("matiere__nom")
        )


class ProgrammeDetailEleveView(RetrieveAPIView):
    """GET /api/eleve/programmes/{id}/ — arbre complet, notions marquées
    a_lecon_publiee. Le queryset restreint à la classe de l'élève fait toute
    la sécurité : un id hors classe n'y figure simplement pas → 404."""

    permission_classes = [IsEleveActif]
    serializer_class = ProgrammeDetailEleveSerializer
    lookup_url_kwarg = "id"

    def get_queryset(self):
        return (
            _programmes_de_la_classe(self.request.user)
            .select_related("matiere", "niveau", "serie")
            .prefetch_related("themes__chapitres__notions__lecon")
        )


class LeconEleveDetailView(RetrieveAPIView):
    """GET /api/eleve/lecons/{id}/ — contenu complet, uniquement si la leçon
    est publiée ET rattachée à la classe de l'élève (les deux conditions sont
    dans le queryset : ni une leçon d'une autre classe, ni un brouillon de SA
    classe, ne peuvent jamais y apparaître)."""

    permission_classes = [IsEleveActif]
    serializer_class = LeconEleveSerializer
    lookup_url_kwarg = "id"

    def get_queryset(self):
        user = self.request.user
        return (
            Lecon.objects.filter(
                statut=Lecon.Statut.PUBLIE,
                notion__chapitre__theme__programme__niveau_id=user.niveau_id,
                notion__chapitre__theme__programme__serie_id=user.serie_id,
            )
            .select_related(
                "notion",
                "notion__chapitre",
                "notion__chapitre__theme",
                "notion__chapitre__theme__programme",
                "notion__chapitre__theme__programme__matiere",
                "notion__chapitre__theme__programme__niveau",
                "notion__chapitre__theme__programme__serie",
            )
            .prefetch_related("exercices", "videos", "ressources")
        )


class MesLeconsView(ListAPIView):
    """GET /api/eleve/mes-lecons/?matiere=&search= — liste plate des leçons
    publiées de SA classe (recherche par titre, filtre par matière)."""

    permission_classes = [IsEleveActif]
    serializer_class = LeconListeEleveSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = (
            Lecon.objects.filter(
                statut=Lecon.Statut.PUBLIE,
                notion__chapitre__theme__programme__niveau_id=user.niveau_id,
                notion__chapitre__theme__programme__serie_id=user.serie_id,
            )
            .select_related(
                "notion",
                "notion__chapitre",
                "notion__chapitre__theme",
                "notion__chapitre__theme__programme",
                "notion__chapitre__theme__programme__niveau",
                "notion__chapitre__theme__programme__serie",
            )
            .order_by("titre")
        )

        matiere_id = self.request.query_params.get("matiere")
        if matiere_id:
            queryset = queryset.filter(notion__chapitre__theme__programme__matiere_id=matiere_id)

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(titre__icontains=search)

        return queryset


class TermeGlossaireEleveDetailView(RetrieveAPIView):
    """GET /api/eleve/glossaire/{slug}/ — 404 générique si le slug n'existe
    pas (le front doit alors rendre [[slug]] comme du texte normal, non
    cliquable, plutôt que de planter)."""

    permission_classes = [IsEleveActif]
    serializer_class = TermeGlossaireEleveSerializer
    lookup_field = "slug"
    lookup_url_kwarg = "slug"
    queryset = TermeGlossaire.objects.select_related(*_LECON_LIEE_SELECT_RELATED)


class TermeGlossaireEleveListeView(ListAPIView):
    """GET /api/eleve/glossaire/?slugs=slug1,slug2,... — plusieurs termes en
    un appel, pour éviter une requête par [[...]] rencontré dans un cours.
    Pas de pagination : c'est un lot ciblé, pas une liste à parcourir.
    Les slugs inconnus sont simplement absents du résultat (pas d'erreur)."""

    permission_classes = [IsEleveActif]
    serializer_class = TermeGlossaireEleveSerializer
    pagination_class = None

    def get_queryset(self):
        slugs_bruts = self.request.query_params.get("slugs", "")
        slugs = [s.strip() for s in slugs_bruts.split(",") if s.strip()]
        if not slugs:
            return TermeGlossaire.objects.none()
        return TermeGlossaire.objects.filter(slug__in=slugs).select_related(*_LECON_LIEE_SELECT_RELATED)
