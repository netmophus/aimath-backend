from django.contrib import admin
from .models import (
    Cycle, Niveau, Serie, Matiere,
    Programme, Theme, Chapitre, Notion,
    Lecon, Exercice, Video, Ressource,
    TermeGlossaire, CharteNotation, PromptSectionNotion,
)


# --- Rangement administratif ---

@admin.register(Cycle)
class CycleAdmin(admin.ModelAdmin):
    list_display = ['nom', 'ordre']


@admin.register(Niveau)
class NiveauAdmin(admin.ModelAdmin):
    list_display = ['nom', 'cycle', 'ordre']
    list_filter = ['cycle']


@admin.register(Serie)
class SerieAdmin(admin.ModelAdmin):
    list_display = ['nom', 'niveau']
    list_filter = ['niveau']


@admin.register(Matiere)
class MatiereAdmin(admin.ModelAdmin):
    list_display = ['nom']


# --- Programme officiel : édition imbriquée ---

class NotionInline(admin.StackedInline):
    model = Notion
    extra = 1


class ChapitreAdmin(admin.ModelAdmin):
    list_display = ['titre', 'theme', 'ordre']
    list_filter = ['theme__programme']
    inlines = [NotionInline]


class ChapitreInline(admin.TabularInline):
    model = Chapitre
    extra = 1


class ThemeAdmin(admin.ModelAdmin):
    list_display = ['titre', 'programme', 'volume_horaire', 'ordre']
    list_filter = ['programme']
    inlines = [ChapitreInline]


class ThemeInline(admin.TabularInline):
    model = Theme
    extra = 1


@admin.register(Programme)
class ProgrammeAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'matiere', 'niveau', 'serie']
    list_filter = ['matiere', 'niveau']
    inlines = [ThemeInline]


admin.site.register(Chapitre, ChapitreAdmin)
admin.site.register(Theme, ThemeAdmin)
admin.site.register(Notion)


# --- Contenu produit : leçon et ses éléments ---

class ExerciceInline(admin.StackedInline):
    model = Exercice
    extra = 1


class VideoInline(admin.TabularInline):
    model = Video
    extra = 1


class RessourceInline(admin.TabularInline):
    model = Ressource
    extra = 1


@admin.register(Lecon)
class LeconAdmin(admin.ModelAdmin):
    list_display = ['titre', 'notion', 'statut', 'est_gratuit', 'modifie_le']
    list_filter = ['statut', 'est_gratuit']
    search_fields = ['titre']
    filter_horizontal = ['prerequis_lecons']
    fields = [
        'notion', 'titre',
        'histoire',
        'objectifs_pedagogiques',
        'prerequis_texte', 'prerequis_lecons',
        'cours_redige', 'demonstrations', 'a_retenir', 'sujet_examen',
        'statut', 'est_gratuit',
    ]
    inlines = [ExerciceInline, VideoInline, RessourceInline]


# --- Glossaire ---

@admin.register(TermeGlossaire)
class TermeGlossaireAdmin(admin.ModelAdmin):
    list_display = ['terme', 'slug', 'lecon_liee', 'modifie_le']
    search_fields = ['terme']
    prepopulated_fields = {'slug': ('terme',)}


# --- Génération IA : charte de notation ---

@admin.register(CharteNotation)
class CharteNotationAdmin(admin.ModelAdmin):
    """Édition de la charte injectée dans les prompts IA. Activer une charte
    ici désactive automatiquement les autres (voir CharteNotation.save())."""

    list_display = ['libelle', 'active', 'modifie_le']
    list_filter = ['active']
    fields = ['libelle', 'active', 'contenu', 'cree_le', 'modifie_le']
    readonly_fields = ['cree_le', 'modifie_le']


@admin.register(PromptSectionNotion)
class PromptSectionNotionAdmin(admin.ModelAdmin):
    """Prompts personnalisés par notion × section — voir aussi l'écran dédié
    dans l'éditeur de leçon du front admin (plus pratique au quotidien)."""

    list_display = ['notion', 'section', 'modifie_le']
    list_filter = ['section']
    search_fields = ['notion__titre']
    fields = ['notion', 'section', 'texte', 'cree_le', 'modifie_le']
    readonly_fields = ['cree_le', 'modifie_le']