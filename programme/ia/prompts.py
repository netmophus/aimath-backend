"""Construction des prompts IA, section par section, pour une Notion donnée.

Chaque section a : le champ correspondant sur Lecon (pour aller chercher
l'exemple few-shot dans la LEÇON MODÈLE), un libellé humain, des consignes de
format spécifiques, et un indicateur "sortie JSON" (seule la section
"exercices" en a besoin — voir SECTIONS["exercices"]).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from django.conf import settings

from ..models import Lecon, Notion
from .exceptions import IAConfigurationInvalide, SectionInconnue

SYSTEM_COMMUN = """Tu es un professeur de mathématiques expert du programme officiel \
du Niger (enseignement secondaire, second cycle), rédacteur de contenu pour \
la plateforme d'apprentissage FAHIMTANA.

RÈGLES ABSOLUES :
- Tu rédiges UNIQUEMENT ce qui est exigible d'après les colonnes officielles \
fournies plus bas (contenus / objectifs / commentaires officiels) — jamais \
au-delà de ce que couvre le programme, jamais en-deçà de ce qui est exigé.
- Tu respectes STRICTEMENT la charte de notation ci-dessous. Toute formule \
qui la contredit (notation anglo-saxonne, gras pour un vecteur, `(a,b)` pour \
un intervalle ouvert, `P(A|B)`…) est une erreur grave.
- Sortie en Markdown, formules en LaTeX destinées à un rendu KaTeX.
- Tu écris en français, avec la rigueur et le ton d'un manuel scolaire \
nigérien — jamais familier, jamais approximatif.

CHARTE DE NOTATION EN VIGUEUR :
{charte}
"""

CHARTE_ABSENTE = (
    "(Aucune charte n'est encore enregistrée en base — applique par défaut "
    "les conventions françaises usuelles : ℝ/ℕ/ℤ/ℚ/ℂ en \\mathbb{}, "
    "intervalles ]a,b[, P_B(A) pour une probabilité conditionnelle, "
    "\\leqslant/\\geqslant, \\ln pour le logarithme népérien.)"
)


@dataclass(frozen=True)
class SectionSpec:
    cle: str
    libelle: str
    champ_lecon: str  # attribut sur Lecon utilisé pour le few-shot (ignoré si sortie_json)
    consignes: str
    sortie_json: bool = False
    verifiable: bool = False  # section mathématique éligible à /verifier/


# Contrat de sortie JSON strict de la section "exercices", isolé dans sa
# propre constante pour pouvoir être ré-injecté APRÈS un prompt personnalisé
# (voir construire_prompt) : _parser_exercices (programme.ia.service) dépend
# de cette structure exacte pour parser la réponse — un prompt personnalisé
# ne doit jamais pouvoir la faire disparaître, seulement piloter le contenu
# pédagogique des exercices générés.
CONTRAT_JSON_EXERCICES = """FORMAT ATTENDU (section : exercices) — SORTIE JSON STRICTE :
Réponds UNIQUEMENT par un tableau JSON valide, SANS texte autour et SANS \
balises ```json, de la forme exacte :
[
  {"enonce": "...", "corrige": "...", "difficulte": "facile"},
  {"enonce": "...", "corrige": "...", "difficulte": "moyen"},
  {"enonce": "...", "corrige": "...", "difficulte": "difficile"}
]
- Exactement 3 exercices, gradués : un facile, un moyen, un difficile — tous \
strictement dans le cadre du programme officiel donné plus bas.
- "enonce" et "corrige" : Markdown + LaTeX, en respectant la charte de \
notation. Comme ce sont des chaînes JSON, ÉCHAPPE les antislashs LaTeX \
(exemple : `\\\\ln`, `\\\\dfrac`, `\\\\int`) pour produire un JSON valide.
- "difficulte" ∈ "facile" | "moyen" | "difficile" exactement (en minuscules, \
sans accent)."""


SECTIONS: dict[str, SectionSpec] = {
    "histoire": SectionSpec(
        cle="histoire",
        libelle="histoire de la notion",
        champ_lecon="histoire",
        consignes="""FORMAT ATTENDU (section : histoire de la notion) :
- Un texte narratif de quelques paragraphes en Markdown : contexte \
historique, mathématicien(s) impliqué(s), problème d'origine ayant motivé \
cette notion, usages actuels. Objectif : donner du sens avant d'attaquer le \
cours.
- 90 % de prose claire qui raconte et contextualise ; les formules, si \
utiles, restent ponctuelles.
- Réponds UNIQUEMENT avec le contenu Markdown, sans préambule ni commentaire \
méta ("voici le texte", etc.).""",
    ),
    "objectifs": SectionSpec(
        cle="objectifs",
        libelle="objectifs pédagogiques",
        champ_lecon="objectifs_pedagogiques",
        consignes="""FORMAT ATTENDU (section : objectifs pédagogiques) :
- Reformule les objectifs officiels en objectifs pour l'élève, à la 2e \
personne ("À la fin de cette leçon, tu sais...", "tu es capable de...").
- Une liste à puces Markdown, concise, un objectif par ligne.
- Réponds UNIQUEMENT avec le Markdown, sans préambule.""",
    ),
    "prerequis": SectionSpec(
        cle="prerequis",
        libelle="prérequis",
        champ_lecon="prerequis_texte",
        consignes="""FORMAT ATTENDU (section : prérequis) :
- Un court texte Markdown (quelques lignes, éventuellement une liste à \
puces) listant ce que l'élève doit déjà maîtriser avant d'aborder cette \
notion (notions antérieures, techniques de calcul).
- Réponds UNIQUEMENT avec le Markdown, sans préambule.""",
    ),
    "cours": SectionSpec(
        cle="cours",
        libelle="cours rédigé",
        champ_lecon="cours_redige",
        verifiable=True,
        consignes="""FORMAT ATTENDU (section : cours rédigé) :
- Structure le cours en sous-parties numérotées avec des titres Markdown \
`###` (ex. "### 1.1 Définition", "### 1.2 Propriétés"), à l'image d'un cours \
de manuel scolaire. Le titre de la leçon est déjà géré séparément par \
l'application : NE COMMENCE PAS par un titre `#` ou `##`, attaque \
directement par le premier `###`. N'utilise AUCUN titre de niveau 1 ou 2 \
(`#`/`##`) nulle part dans le texte — seulement `###` et en-dessous.
- Inclus définitions, propriétés énoncées (les démonstrations détaillées \
font l'objet d'une AUTRE section, ne les développe pas ici), et au moins un \
exemple résolu par notion clé.
- 90 % de prose qui explique et paraphrase ; les formules display suivent \
la règle de la charte ($$ seul sur sa ligne, formule sur la ligne suivante, \
$$ seul en fermeture).
- Réponds UNIQUEMENT avec le contenu Markdown du cours, sans préambule ni \
commentaire méta.""",
    ),
    "demonstrations": SectionSpec(
        cle="demonstrations",
        libelle="démonstrations",
        champ_lecon="demonstrations",
        verifiable=True,
        consignes="""FORMAT ATTENDU (section : démonstrations) :
- Rédige, une à une, les démonstrations des propriétés/théorèmes exigibles \
par le programme pour cette notion, chacune sous un titre `###`.
- Rigueur non négociable : chaque étape de calcul doit être juste, justifiée, \
et enchaînée logiquement (pas de saut d'étape qui laisse un doute).
- Réponds UNIQUEMENT avec le Markdown, sans préambule.""",
    ),
    "a_retenir": SectionSpec(
        cle="a_retenir",
        libelle="à retenir",
        champ_lecon="a_retenir",
        consignes="""FORMAT ATTENDU (section : à retenir) :
- Une synthèse courte et dense (encadré de fin de cours) : uniquement les \
formules et résultats clés à mémoriser, en Markdown (listes à puces et/ou \
tableau). Ne redémontre rien, ne réexplique rien.
- Réponds UNIQUEMENT avec le Markdown, sans préambule.""",
    ),
    "exercices": SectionSpec(
        cle="exercices",
        libelle="exercices",
        champ_lecon="",  # traité à part : few-shot = les 3 exercices de la leçon modèle
        sortie_json=True,
        verifiable=True,
        consignes=CONTRAT_JSON_EXERCICES,
    ),
    "sujet_examen": SectionSpec(
        cle="sujet_examen",
        libelle="sujet type examen",
        champ_lecon="sujet_examen",
        verifiable=True,
        consignes="""FORMAT ATTENDU (section : sujet type examen) :
- Commence par un en-tête de deux lignes, AVANT le premier exercice, \
indiquant la durée indicative (ex. "Durée : 1 heure") et le barème total \
(ex. "Barème : /20").
- Puis 2 à 4 exercices notés, de difficulté CROISSANTE, chacun sous un titre \
`### Exercice N (X points)` — la somme des points de tous les exercices doit \
être exactement égale au barème total annoncé en en-tête.
- Chaque exercice reste STRICTEMENT dans le périmètre de la notion (mêmes \
colonnes officielles que pour les autres sections) — jamais une notion non \
encore couverte par le programme.
- Après le dernier exercice, un titre `## Corrigé` (EXACTEMENT ce texte, \
rien d'autre après "Corrigé") introduit la partie corrigée : reprends CHAQUE \
exercice, dans l'ordre, avec une résolution détaillée et rédigée (pas \
seulement le résultat final) — même rigueur que pour la section \
"démonstrations". À l'intérieur du corrigé, N'UTILISE AUCUN sous-titre \
Markdown (pas de `###`) pour séparer les exercices — introduis chacun par \
une phrase ou un texte en gras ("**Exercice 1.**"), en prose continue.
- N'utilise AUCUN titre de niveau 1 (`#`) ; le titre de la leçon est déjà \
géré par l'application. `##` est réservé au seul titre "Corrigé" de cette \
section — les exercices de l'énoncé utilisent `###`, jamais `##`.
- Réponds UNIQUEMENT avec le contenu Markdown, sans préambule ni commentaire \
méta.""",
    ),
}


def _lecon_modele() -> Lecon:
    try:
        return Lecon.objects.get(notion_id=settings.IA_NOTION_MODELE_ID)
    except Lecon.DoesNotExist as exc:
        raise IAConfigurationInvalide(
            "La leçon modèle (réglage IA_NOTION_MODELE_ID) est introuvable en base."
        ) from exc


def _bloc_exemple_texte(spec: SectionSpec) -> str:
    lecon = _lecon_modele()
    valeur = (getattr(lecon, spec.champ_lecon, "") or "").strip()
    if not valeur:
        return ""
    return f"""EXEMPLE DE NIVEAU ATTENDU (extrait d'une autre leçon déjà validée — sert de \
référence de style, de rigueur et de longueur ; le sujet mathématique est \
différent, ne recopie pas son contenu) :
---
{valeur}
---"""


def _bloc_exemple_exercices() -> str:
    lecon = _lecon_modele()
    exercices = list(lecon.exercices.order_by("ordre").values("enonce", "corrige", "difficulte"))
    if not exercices:
        return ""
    exemple_json = json.dumps(exercices, ensure_ascii=False, indent=2)
    return f"""EXEMPLE DE FORMAT ET DE NIVEAU ATTENDUS (exercices d'une autre leçon déjà \
validée — même structure JSON à respecter, sujet mathématique différent) :
---
{exemple_json}
---"""


def construire_contexte_notion(notion: Notion) -> str:
    chapitre = notion.chapitre
    theme = chapitre.theme
    programme = theme.programme
    classe = programme.niveau.nom
    if programme.serie_id:
        classe = f"{classe} {programme.serie.nom}"
    return f"""CONTEXTE :
- Matière : {programme.matiere.nom}
- Classe : {classe}
- Thème : {theme.titre}
- Chapitre : {chapitre.titre}
- Notion : {notion.titre}

PROGRAMME OFFICIEL POUR CETTE NOTION (ta seule source de vérité — ne rédige \
que ce qui en relève) :
- Contenus officiels : {notion.contenus_officiels or "(non renseigné)"}
- Objectifs officiels : {notion.objectifs_officiels or "(non renseigné)"}
- Commentaires officiels : {notion.commentaires_officiels or "(non renseigné)"}"""


def charte_active_texte() -> str:
    from ..models import CharteNotation

    charte = CharteNotation.actuelle()
    return charte.contenu if charte else CHARTE_ABSENTE


def construire_prompt(
    notion: Notion, section: str, prompt_perso: str | None = None
) -> tuple[str, str]:
    """Construit (system_prompt, user_prompt) pour générer `section` sur
    `notion`. Lève SectionInconnue si `section` n'est pas dans SECTIONS.

    `prompt_perso` (texte saisi par l'admin pour CETTE notion × section, voir
    programme.models.PromptSectionNotion) REMPLACE la consigne par défaut de
    la section quand il est fourni et non vide. La charte de notation
    (SYSTEM_COMMUN) et les 3 colonnes officielles (construire_contexte_notion,
    dans le user prompt) restent, elles, TOUJOURS injectées automatiquement —
    non négociable, un prompt perso ne peut ni les retirer ni les affaiblir.

    Cas particulier "exercices" (spec.sortie_json) : même avec un prompt
    perso, CONTRAT_JSON_EXERCICES est toujours présent en fin de consignes —
    le prompt perso pilote le contenu pédagogique des exercices, jamais la
    structure de sortie dont dépend _parser_exercices."""

    spec = SECTIONS.get(section)
    if spec is None:
        raise SectionInconnue(f"Section inconnue : « {section} ».")

    prompt_perso = (prompt_perso or "").strip()

    if spec.sortie_json:
        consignes = f"{prompt_perso}\n\n{CONTRAT_JSON_EXERCICES}" if prompt_perso else spec.consignes
    else:
        consignes = prompt_perso or spec.consignes

    system_prompt = SYSTEM_COMMUN.format(charte=charte_active_texte()) + "\n" + consignes

    bloc_exemple = _bloc_exemple_exercices() if spec.sortie_json else _bloc_exemple_texte(spec)

    parties = [construire_contexte_notion(notion)]
    if bloc_exemple:
        parties.append(bloc_exemple)
    parties.append(f'Rédige maintenant la section "{spec.libelle}" pour CETTE notion.')

    user_prompt = "\n\n".join(parties)
    return system_prompt, user_prompt
