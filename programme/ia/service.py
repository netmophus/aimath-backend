"""Orchestration de haut niveau : construit le prompt, appelle le fournisseur
IA, met en forme le résultat. C'est ce module que les vues (programme/ia_views.py)
appellent — elles ne connaissent ni les prompts, ni le fournisseur.
"""

from __future__ import annotations

import json
import re

from ..models import Notion
from .exceptions import IAErreur, SectionInconnue
from .fournisseurs import appeler_ia
from .prompts import SECTIONS, charte_active_texte, construire_contexte_notion, construire_prompt

DIFFICULTES_VALIDES = {"facile", "moyen", "difficile"}


def generer_section(notion: Notion, section: str) -> str | list[dict]:
    """Génère UNE section pour UNE notion. Renvoie un texte Markdown pour les
    sections texte, ou une liste de {enonce, corrige, difficulte} pour
    "exercices". Ne touche jamais à la base (aucune écriture)."""

    system_prompt, user_prompt = construire_prompt(notion, section)
    reponse = appeler_ia(system_prompt, user_prompt)

    spec = SECTIONS[section]
    if spec.sortie_json:
        return _parser_exercices(reponse.texte)
    return reponse.texte


def _parser_exercices(texte: str) -> list[dict]:
    """Parsing robuste du JSON d'exercices renvoyé par l'IA : elle peut
    l'entourer de ```json … ``` malgré la consigne, ou ajouter une phrase
    avant/après — on nettoie avant de parser, et on échoue avec un message
    FR clair plutôt que de laisser passer une ValueError brute."""

    nettoye = texte.strip()
    nettoye = re.sub(r"^```(?:json)?\s*", "", nettoye)
    nettoye = re.sub(r"\s*```$", "", nettoye).strip()

    debut, fin = nettoye.find("["), nettoye.rfind("]")
    if debut != -1 and fin != -1 and fin > debut:
        nettoye = nettoye[debut : fin + 1]

    try:
        donnees = json.loads(nettoye)
    except json.JSONDecodeError as exc:
        raise IAErreur(
            "La réponse de l'IA pour les exercices n'était pas un JSON valide "
            f"(erreur de parsing : {exc.msg} à la position {exc.pos})."
        ) from exc

    if not isinstance(donnees, list) or not donnees:
        raise IAErreur("La réponse de l'IA pour les exercices doit être une liste non vide d'exercices.")

    exercices = []
    for i, item in enumerate(donnees, start=1):
        if not isinstance(item, dict):
            raise IAErreur(f"Exercice {i} : format inattendu (objet JSON attendu).")
        enonce = str(item.get("enonce", "")).strip()
        corrige = str(item.get("corrige", "")).strip()
        difficulte = str(item.get("difficulte", "")).strip().lower()
        if not enonce or not corrige:
            raise IAErreur(f"Exercice {i} : énoncé ou corrigé manquant dans la réponse de l'IA.")
        if difficulte not in DIFFICULTES_VALIDES:
            raise IAErreur(
                f"Exercice {i} : difficulté « {difficulte} » invalide "
                f"(attendu : {', '.join(sorted(DIFFICULTES_VALIDES))})."
            )
        exercices.append({"enonce": enonce, "corrige": corrige, "difficulte": difficulte})

    return exercices


SYSTEM_VERIFICATION = """Tu es un professeur de mathématiques chevronné, chargé de RELIRE \
un contenu de cours destiné à des élèves du secondaire nigérien, avec un \
regard critique et exigeant.

Ta tâche : repérer les erreurs MATHÉMATIQUES du contenu fourni — un résultat \
faux, une limite incorrecte, une étape de calcul incohérente, un corrigé \
d'exercice erroné, une hypothèse manquante rendant un énoncé faux. Signale \
aussi, plus secondairement, une violation flagrante de la charte de \
notation ci-dessous si tu en vois une.

CHARTE DE NOTATION EN VIGUEUR :
{charte}

FORMAT DE RÉPONSE :
- Si tu détectes un ou plusieurs problèmes : une liste à puces Markdown, une \
puce par problème, chacune identifiant précisément l'endroit concerné (ex. \
citation courte du passage) et expliquant pourquoi c'est faux ou douteux.
- Si tu ne détectes aucun problème manifeste : réponds EXACTEMENT \
"Aucun problème manifeste détecté." (rien d'autre).
- Ne réécris pas le contenu, ne le corrige pas toi-même : tu donnes un avis, \
pas une nouvelle version.
"""


def verifier_contenu(section: str, contenu: str, notion: Notion | None = None) -> str:
    """Demande à l'IA un second regard sur un contenu déjà rédigé (cours,
    démonstrations ou exercices). Renvoie un AVIS texte — jamais une
    validation formelle, voir le system prompt ci-dessus."""

    spec = SECTIONS.get(section)
    if spec is None:
        raise SectionInconnue(f"Section inconnue : « {section} ».")
    if not spec.verifiable:
        raise SectionInconnue(
            f"La vérification IA n'est disponible que pour les sections mathématiques "
            f"({', '.join(s.cle for s in SECTIONS.values() if s.verifiable)})."
        )

    system_prompt = SYSTEM_VERIFICATION.format(charte=charte_active_texte())

    parties = []
    if notion is not None:
        parties.append(construire_contexte_notion(notion))
    parties.append(f"CONTENU À RELIRE (section « {spec.libelle} ») :\n---\n{contenu}\n---")

    reponse = appeler_ia(system_prompt, "\n\n".join(parties))
    return reponse.texte
