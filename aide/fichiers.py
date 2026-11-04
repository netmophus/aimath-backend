"""Contrôle d'une image jointe : taille, type annoncé ET contenu réel (octets magiques), jamais le seul nom de fichier."""

TAILLE_MAX = 5 * 1024 * 1024
TYPES_AUTORISES = ("image/jpeg", "image/png", "image/webp")
MESSAGE_FORMAT = "Format refusé. Utilise JPG, PNG ou WebP."
MESSAGE_TAILLE = "Image trop lourde (5 Mo max)."


def type_reel(octets: bytes) -> str | None:
    if octets[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if octets[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if octets[:4] == b"RIFF" and octets[8:12] == b"WEBP":
        return "image/webp"
    return None


def controler(fichier) -> tuple[bytes, str]:
    """Renvoie (octets, type). Lève ValueError(message) si le fichier est refusé."""
    if fichier.size > TAILLE_MAX:
        raise ValueError(MESSAGE_TAILLE)
    if fichier.size == 0:
        raise ValueError("Image vide.")
    octets = fichier.read(TAILLE_MAX + 1)
    if len(octets) > TAILLE_MAX:
        raise ValueError(MESSAGE_TAILLE)
    reel = type_reel(octets)
    if reel is None or reel not in TYPES_AUTORISES:
        raise ValueError(MESSAGE_FORMAT)
    annonce = (getattr(fichier, "content_type", "") or "").lower()
    if annonce == "image/jpg":
        annonce = "image/jpeg"
    if annonce != reel:
        raise ValueError(MESSAGE_FORMAT)
    return octets, reel
