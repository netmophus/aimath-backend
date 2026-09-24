from django.db import models
from django.utils.text import slugify


# ============================================================
#  RANGEMENT ADMINISTRATIF : où se situe-t-on ?
# ============================================================

class Cycle(models.Model):
    """Premier cycle (6e-3e) ou Second cycle (2nde-Tle)."""
    nom = models.CharField(max_length=50, unique=True)
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['ordre']

    def __str__(self):
        return self.nom


class Niveau(models.Model):
    """Une classe : 6e, 5e … 2nde, 1re, Tle."""
    cycle = models.ForeignKey(Cycle, on_delete=models.PROTECT, related_name='niveaux')
    nom = models.CharField(max_length=50)
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['ordre']
        unique_together = ['cycle', 'nom']

    def __str__(self):
        return self.nom


class Serie(models.Model):
    """C, D, E, A, G… Rattachée à un niveau. Facultative (la 6e n'en a pas)."""
    niveau = models.ForeignKey(Niveau, on_delete=models.PROTECT, related_name='series')
    nom = models.CharField(max_length=10)

    class Meta:
        unique_together = ['niveau', 'nom']

    def __str__(self):
        return f"{self.niveau} {self.nom}"


class Matiere(models.Model):
    """Mathématiques, Physique, Français…"""
    nom = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nom


# ============================================================
#  LE PROGRAMME OFFICIEL : figé, jamais modifié par l'IA
# ============================================================

class Programme(models.Model):
    """Le référentiel officiel pour une Matière × un Niveau × (une Série)."""
    matiere = models.ForeignKey(Matiere, on_delete=models.PROTECT, related_name='programmes')
    niveau = models.ForeignKey(Niveau, on_delete=models.PROTECT, related_name='programmes')
    serie = models.ForeignKey(
        Serie, on_delete=models.PROTECT, related_name='programmes',
        null=True, blank=True   # null pour le premier cycle sans série
    )

    class Meta:
        unique_together = ['matiere', 'niveau', 'serie']

    def __str__(self):
        cible = self.serie if self.serie else self.niveau
        return f"{self.matiere} — {cible}"


class Theme(models.Model):
    """Grand bloc du programme (ex: 'Organisation des données', 68h)."""
    programme = models.ForeignKey(Programme, on_delete=models.CASCADE, related_name='themes')
    titre = models.CharField(max_length=255)
    volume_horaire = models.PositiveSmallIntegerField(null=True, blank=True)
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['ordre']

    def __str__(self):
        return self.titre


class Chapitre(models.Model):
    """Chapitre dans un thème (ex: 'Fonctions logarithmes')."""
    theme = models.ForeignKey(Theme, on_delete=models.CASCADE, related_name='chapitres')
    titre = models.CharField(max_length=255)
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['ordre']

    def __str__(self):
        return self.titre


class Notion(models.Model):
    """Point précis du programme, avec les 3 colonnes officielles."""
    chapitre = models.ForeignKey(Chapitre, on_delete=models.CASCADE, related_name='notions')
    titre = models.CharField(max_length=255)
    ordre = models.PositiveSmallIntegerField(default=0)

    contenus_officiels = models.TextField(blank=True)
    objectifs_officiels = models.TextField(blank=True)      # un objectif par ligne
    commentaires_officiels = models.TextField(blank=True)

    class Meta:
        ordering = ['ordre']

    def __str__(self):
        return self.titre


# ============================================================
#  LE CONTENU PRODUIT : vivant, rédigé par l'IA, validé par toi
# ============================================================

class Lecon(models.Model):
    """Le cours réellement rédigé pour une notion. Une notion → une leçon."""

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        A_VALIDER = 'a_valider', 'À valider'
        PUBLIE = 'publie', 'Publié'

    notion = models.OneToOneField(Notion, on_delete=models.CASCADE, related_name='lecon')
    titre = models.CharField(max_length=255)

    # "Pourquoi cette notion ?" : contexte historique, enjeux, usages — en
    # ouverture du gabarit, avant les objectifs pédagogiques.
    histoire = models.TextField(blank=True, default="")     # Markdown + LaTeX

    objectifs_pedagogiques = models.TextField(blank=True)

    # Prérequis : texte libre (usage principal, ex. "maîtriser la dérivation…")
    # + liens optionnels vers d'autres leçons (usage secondaire, pour plus tard).
    prerequis_texte = models.TextField(blank=True, default="")   # Markdown
    prerequis_lecons = models.ManyToManyField('self', blank=True, symmetrical=False)

    cours_redige = models.TextField(blank=True)             # Markdown + LaTeX
    demonstrations = models.TextField(blank=True)           # Markdown + LaTeX
    a_retenir = models.TextField(blank=True, default="")    # Markdown + LaTeX

    # Sujet type examen : énoncé noté (2-4 exercices, barème) + corrigé rédigé,
    # séparés par un titre "## Corrigé" dans le Markdown (voir
    # programme.ia.prompts.SECTIONS["sujet_examen"]) — c'est ce titre que le
    # front élève repère pour flouter uniquement la partie corrigé, comme les
    # corrigés d'exercices (voir components/eleve/CarteCorrigeExamen.tsx).
    sujet_examen = models.TextField(blank=True, default="")  # Markdown + LaTeX

    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.BROUILLON
    )
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.titre


class Exercice(models.Model):
    """Exercice rattaché à une leçon, avec corrigé masquable."""

    class Difficulte(models.TextChoices):
        FACILE = 'facile', 'Facile'
        MOYEN = 'moyen', 'Moyen'
        DIFFICILE = 'difficile', 'Difficile'

    lecon = models.ForeignKey(Lecon, on_delete=models.CASCADE, related_name='exercices')
    enonce = models.TextField()                             # Markdown + LaTeX
    corrige = models.TextField(blank=True)                  # Markdown + LaTeX
    difficulte = models.CharField(
        max_length=20, choices=Difficulte.choices, default=Difficulte.MOYEN
    )
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['ordre']

    def __str__(self):
        return f"Exercice {self.ordre} — {self.lecon.titre}"


class Video(models.Model):
    """Lien vidéo rattaché à une leçon."""
    lecon = models.ForeignKey(Lecon, on_delete=models.CASCADE, related_name='videos')
    titre = models.CharField(max_length=255)
    url = models.URLField()
    description = models.TextField(blank=True)
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['ordre']

    def __str__(self):
        return self.titre


class Ressource(models.Model):
    """Fichier ou lien complémentaire (fiche, annale…) rattaché à une leçon."""
    lecon = models.ForeignKey(Lecon, on_delete=models.CASCADE, related_name='ressources')
    titre = models.CharField(max_length=255)
    fichier = models.FileField(upload_to='ressources/', null=True, blank=True)
    url = models.URLField(blank=True)
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['ordre']

    def __str__(self):
        return self.titre


# ============================================================
#  GLOSSAIRE : termes réutilisables, rendus cliquables dans le cours
# ============================================================

class TermeGlossaire(models.Model):
    """Un terme partagé (définition + exemple + lien optionnel vers une leçon)
    que le cours peut référencer via la syntaxe [[slug]] pour ouvrir une
    modale explicative côté élève. Un même terme peut donc être réutilisé
    dans plusieurs leçons sans dupliquer sa définition."""

    terme = models.CharField(max_length=255)
    # Clé stable utilisée dans la syntaxe [[slug]] du cours — dérivée de
    # `terme` à la création si absente (voir save()), jamais recalculée
    # ensuite pour ne pas casser les [[slug]] déjà écrits dans un cours.
    slug = models.SlugField(unique=True, blank=True, max_length=255)
    definition = models.TextField()                          # Markdown + LaTeX, obligatoire
    exemple = models.TextField(blank=True, default="")        # Markdown + LaTeX, optionnel
    lecon_liee = models.ForeignKey(
        Lecon, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='termes_glossaire',
    )
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['terme']

    def __str__(self):
        return self.terme

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._slug_unique()
        super().save(*args, **kwargs)

    def _slug_unique(self) -> str:
        """Dérive un slug depuis `terme` et garantit son unicité par
        suffixe numérique (-2, -3…) en cas de collision."""
        base = slugify(self.terme) or 'terme'
        slug = base
        suffixe = 2
        deja_pris = TermeGlossaire.objects.exclude(pk=self.pk)
        while deja_pris.filter(slug=slug).exists():
            slug = f"{base}-{suffixe}"
            suffixe += 1
        return slug


# ============================================================
#  GÉNÉRATION IA : réglages éditables depuis l'admin
# ============================================================

class CharteNotation(models.Model):
    """La charte de notation mathématique (Markdown), injectée dans le
    system prompt à chaque génération IA d'une section de leçon.

    Singleton logique : une seule charte est "active" à la fois (`active`).
    À l'enregistrement, activer une charte désactive automatiquement les
    autres — pas de contrainte unique en base, juste une garantie applicative
    (voir save()), suffisante pour un usage piloté depuis l'admin Django.
    """

    libelle = models.CharField(max_length=255, default="Charte de notation")
    contenu = models.TextField(
        help_text="Markdown. Injecté tel quel dans le prompt système envoyé à l'IA."
    )
    active = models.BooleanField(
        default=True,
        help_text="Une seule charte active à la fois : l'activer désactive les autres.",
    )
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "charte de notation"
        verbose_name_plural = "chartes de notation"
        ordering = ['-modifie_le']

    def __str__(self):
        return f"{self.libelle} {'(active)' if self.active else ''}".strip()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.active:
            CharteNotation.objects.exclude(pk=self.pk).update(active=False)

    @classmethod
    def actuelle(cls) -> "CharteNotation | None":
        """La charte à utiliser dans les prompts : la plus récente parmi les
        actives, ou None si aucune n'existe encore en base."""
        return cls.objects.filter(active=True).order_by('-modifie_le').first()


class PromptSectionNotion(models.Model):
    """Prompt de génération IA personnalisé, pour UNE notion et UNE section
    (histoire, cours, exercices…). Quand une ligne existe pour ce couple,
    son `texte` REMPLACE la consigne par défaut de la section (voir
    programme.ia.prompts.SECTIONS) — la charte de notation et les 3 colonnes
    officielles de la notion restent, elles, TOUJOURS injectées
    automatiquement, quel que soit ce prompt (voir construire_prompt).
    Absence de ligne pour ce couple = comportement de génération par défaut.

    Rattachée à la Notion (pas à la Lecon) : la génération elle-même
    s'appuie sur la Notion, indépendamment de l'existence d'une leçon
    (voir programme.ia_views._recuperer_notion).

    `section` n'a volontairement pas de `choices=` ici : la liste des
    sections valides vit dans programme.ia.prompts.SECTIONS, et l'importer
    ici créerait un import circulaire (prompts.py importe déjà ce module
    pour Notion/Lecon). La validation des clés se fait au niveau du
    serializer (programme.prompt_ia_serializers), comme pour
    programme.ia_serializers.SECTIONS_CHOICES.
    """

    notion = models.ForeignKey(
        Notion, on_delete=models.CASCADE, related_name='prompts_personnalises'
    )
    section = models.CharField(max_length=20)
    texte = models.TextField()
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "prompt personnalisé"
        verbose_name_plural = "prompts personnalisés"
        unique_together = ['notion', 'section']
        ordering = ['notion_id', 'section']

    def __str__(self):
        return f"prompt {self.section} — {self.notion}"