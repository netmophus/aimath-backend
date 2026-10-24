"""Génération de mots de passe temporaires (réinitialisation par un admin)."""

import secrets

# Alphabet sans caractères ambigus à la lecture d'un SMS : ni 0/O, ni 1/I/l.
ALPHABET_LISIBLE = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"


def generer_mot_de_passe(longueur: int = 10) -> str:
    """Mot de passe aléatoire (module `secrets`, cryptographiquement sûr),
    avec au moins une majuscule, une minuscule et un chiffre."""
    while True:
        mot_de_passe = "".join(secrets.choice(ALPHABET_LISIBLE) for _ in range(longueur))
        if (
            any(c.isupper() for c in mot_de_passe)
            and any(c.islower() for c in mot_de_passe)
            and any(c.isdigit() for c in mot_de_passe)
        ):
            return mot_de_passe
