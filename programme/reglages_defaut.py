"""
Aide pour les tests : lire les valeurs PAR DÉFAUT des réglages IA / simulations, indépendamment du .env local.

`config.settings` lit le .env via python-decouple ; un développeur qui active ses fonctions IA en local
(IA_*_ACTIVE=True) ferait donc échouer les tests « la valeur par défaut est désactivée » alors que le code est
correct. On recharge ici une COPIE de settings.py où seules les clés IA_* et SIMULATIONS_* sont ignorées (le reste
du .env, SECRET_KEY, base de données…, est lu normalement). Le vrai module `config.settings` n'est pas touché.
"""

import importlib.util
import os
from pathlib import Path
from types import ModuleType
from unittest import mock

from decouple import Config, RepositoryEnv

PREFIXES_IGNORES = ("IA_", "SIMULATIONS_")
RACINE = Path(__file__).resolve().parent.parent


class _DepotSansReglagesIA(RepositoryEnv):
    def __contains__(self, key):
        return not key.startswith(PREFIXES_IGNORES) and super().__contains__(key)

    def __getitem__(self, key):
        if key.startswith(PREFIXES_IGNORES):
            raise KeyError(key)
        return super().__getitem__(key)


def reglages_par_defaut() -> ModuleType:
    env_propre = {k: v for k, v in os.environ.items() if not k.startswith(PREFIXES_IGNORES)}
    config_isolee = Config(_DepotSansReglagesIA(str(RACINE / ".env")))
    with mock.patch.dict(os.environ, env_propre, clear=True), mock.patch("decouple.config", config_isolee):
        spec = importlib.util.spec_from_file_location("settings_valeurs_par_defaut", RACINE / "config" / "settings.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module
