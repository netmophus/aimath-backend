"""Segmentation SMS : GSM-7 (160 / 153 caractères par segment) ou Unicode (70 / 67).

Un seul caractère hors GSM-7 (par exemple "ê", "ô", "î", "â" ou l'apostrophe typographique) fait passer
TOUT le message en Unicode : il coûte alors souvent plus de segments. L'estimation est indicative, le
fournisseur reste seul juge de la facturation réelle.
"""

_BASE = (
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
_ETENDU = "^{}\[~]|€\f"   # comptent pour 2 caractères


def est_gsm7(texte: str) -> bool:
    return all(c in _BASE or c in _ETENDU for c in texte)


def compter(texte: str) -> dict:
    """{"caracteres", "unicode", "segments"} ; un texte vide donne 0 segment."""
    if not texte:
        return {"caracteres": 0, "unicode": False, "segments": 0}
    if est_gsm7(texte):
        unites = sum(2 if c in _ETENDU else 1 for c in texte)
        segments = 1 if unites <= 160 else -(-unites // 153)
        return {"caracteres": len(texte), "unicode": False, "segments": segments}
    unites = len(texte.encode("utf-16-le")) // 2   # les caractères hors plan de base comptent double
    segments = 1 if unites <= 70 else -(-unites // 67)
    return {"caracteres": len(texte), "unicode": True, "segments": segments}
