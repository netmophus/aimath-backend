"""Ressources du worker : connexions PostgreSQL et mémoire pendant un traitement parallèle (fournisseur simulé)."""

import ctypes
import os
import threading
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.db import connection
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient

from budget_ia.tests.outils import creer_eleve, creer_programme_maths
from traitement_ia.models import TacheIA
from traitement_ia.tests.test_taches import ANALYSE, REGLAGES, faux_sdk


def memoire_pic_mo() -> float | None:
    """Pic de mémoire du processus (Windows : GetProcessMemoryInfo ; Linux : /proc). None si indisponible."""
    try:
        if os.name == "nt":
            class PMC(ctypes.Structure):
                _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong), ("PeakWorkingSetSize", ctypes.c_size_t),
                            ("WorkingSetSize", ctypes.c_size_t), ("a", ctypes.c_size_t), ("b", ctypes.c_size_t), ("c", ctypes.c_size_t),
                            ("d", ctypes.c_size_t), ("e", ctypes.c_size_t), ("f", ctypes.c_size_t)]
            pmc = PMC()
            pmc.cb = ctypes.sizeof(PMC)
            from ctypes import wintypes
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.GetCurrentProcess.restype = wintypes.HANDLE
            k32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
            k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
            return pmc.PeakWorkingSetSize / 1e6
        with open("/proc/self/status") as f:
            return next(int(l.split()[1]) for l in f if l.startswith("VmHWM")) / 1000
    except Exception:  # noqa: BLE001
        return None


class RessourcesDuWorkerTests(TransactionTestCase):
    @override_settings(**REGLAGES)
    def test_connexions_postgresql_et_memoire_avec_quatre_threads(self):
        cache.clear()
        eleve, programme = creer_programme_maths()
        eleves = [eleve] + [creer_eleve(f"+2279000008{i}", niveau=programme.niveau, serie=programme.serie) for i in range(3)]
        mesures, tous_la, libere = [], threading.Barrier(4, timeout=30), threading.Event()

        def lent(nom):
            tous_la.wait()            # les 4 threads sont EN MÊME TEMPS au milieu d'un appel IA
            with connection.cursor() as c:
                pass
            mesures.append(True)
            libere.wait(timeout=0.2)

        client = faux_sdk(analyse=ANALYSE, action=lent)
        with mock.patch("anthropic.Anthropic", return_value=client):
            for i, e in enumerate(eleves):
                api = APIClient()
                api.force_authenticate(e)
                api.post("/api/eleve/resoudre/", {"programme": programme.id, "mode": "correction", "enonce": f"exercice {i} : x^2={i + 1}", "analyser": "true"}, format="multipart")
            relevé = {}

            def sonde():
                tous_la_ok = threading.Event()
                for _ in range(100):
                    if len(mesures) >= 0 and client.appels:
                        with connection.cursor() as c:
                            c.execute("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()")
                            relevé["max"] = max(relevé.get("max", 0), c.fetchone()[0])
                    libere.wait(0.05)
                connection.close()

            s = threading.Thread(target=sonde)
            s.start()
            call_command("traiter_taches_ia", "--une-fois", "--threads", "4")
            libere.set()
            s.join(30)
        self.assertEqual(TacheIA.objects.filter(statut="terminee").count(), 4)
        # 4 threads du worker + le thread principal + la sonde (+ marge de l'infrastructure de test) : borné et connu.
        self.assertLessEqual(relevé.get("max", 0), 4 + 3)
        pic = memoire_pic_mo()
        print(f"\n[ressources] connexions PostgreSQL max observées : {relevé.get('max')} ; pic mémoire du processus de test : {pic and round(pic)} Mo")
        if pic is not None:
            self.assertLess(pic, 450)   # le dyno Basic offre 512 Mo
