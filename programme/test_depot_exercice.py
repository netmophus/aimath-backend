"""
Tests de POST /api/eleve/resoudre/ (étape 3 : réception + validation seule).

Chaque test d'erreur vérifie aussi que le message est en français ; les tests
« rien n'est enregistré / transmis » surveillent le disque (MEDIA_ROOT) et les
appels réseau/IA, en plus du contenu de la réponse.
"""

import os
import tempfile
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from comptes.models import User

from .models import Cycle, Matiere, Niveau, Programme, Serie

URL = "/api/eleve/resoudre/"

# Limites écrites EN DUR (pas importées du code testé) : si quelqu'un les change
# dans exercice_serializers.py, ces tests doivent le signaler.
NB_MAX_IMAGES = 6
TAILLE_MAX_FICHIER_OCTETS = 10 * 1024 * 1024
LONGUEUR_MAX_ENONCE = 4000

JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 64
PDF = b"%PDF-1.4\n" + b"%\xe2\xe3\xcf\xd3\n" * 4 + b"%%EOF\n"


def fichier(nom: str, contenu: bytes, type_declare: str = "application/octet-stream") -> SimpleUploadedFile:
    return SimpleUploadedFile(nom, contenu, content_type=type_declare)


def image(i: int = 1) -> SimpleUploadedFile:
    return fichier(f"page{i}.jpg", JPEG, "image/jpeg")


class DepotExerciceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cycle = Cycle.objects.create(nom="Second cycle", ordre=2)
        tle = Niveau.objects.create(cycle=cycle, nom="Terminale", ordre=7)
        cls.serie_c = Serie.objects.create(niveau=tle, nom="C")
        cls.serie_d = Serie.objects.create(niveau=tle, nom="D")

        maths = Matiere.objects.create(nom="Mathématiques")
        physique = Matiere.objects.create(nom="Physique")
        histoire = Matiere.objects.create(nom="Histoire")

        cls.maths_c = Programme.objects.create(matiere=maths, niveau=tle, serie=cls.serie_c)
        cls.physique_c = Programme.objects.create(matiere=physique, niveau=tle, serie=cls.serie_c)
        cls.histoire_c = Programme.objects.create(matiere=histoire, niveau=tle, serie=cls.serie_c)
        cls.maths_d = Programme.objects.create(matiere=maths, niveau=tle, serie=cls.serie_d)

        def eleve(tel, **extra):
            return User.objects.create_user(
                tel, password="Motdepasse-2026", prenom="E", nom="L",
                role=User.Role.ELEVE, statut=extra.pop("statut", User.Statut.ACTIF),
                niveau=tle, serie=extra.pop("serie", cls.serie_c), **extra,
            )

        cls.eleve_c = eleve("+22790000001")
        cls.eleve_attente = eleve("+22790000002", statut=User.Statut.EN_ATTENTE)
        cls.enseignant = User.objects.create_user(
            "+22790000003", password="Motdepasse-2026", prenom="P", nom="R",
            role=User.Role.ENSEIGNANT, statut=User.Statut.ACTIF,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.eleve_c)

    def deposer(self, **champs):
        corps = {"programme": self.maths_c.id, "mode": "correction"}
        corps.update(champs)
        corps = {k: v for k, v in corps.items() if v is not None}
        return self.client.post(URL, corps, format="multipart")

    def messages(self, reponse, champ) -> str:
        return " ".join(str(m) for m in reponse.json()[champ])

    # --- Cas valides -------------------------------------------------------

    def test_texte_seul_est_valide_mais_ni_enregistre_ni_traite(self):
        reponse = self.deposer(enonce="Résoudre dans R : x² - 5x + 6 = 0", mode="professeur")

        self.assertEqual(reponse.status_code, 200)
        corps = reponse.json()
        self.assertIs(corps["valide"], True)
        self.assertIs(corps["enregistre"], False)
        self.assertIs(corps["traite"], False)
        self.assertIn("pas encore été enregistré ni traité", corps["message"])
        recap = corps["recapitulatif"]
        self.assertEqual(recap["mode"], "professeur")
        self.assertEqual(recap["nb_fichiers"], 0)
        self.assertEqual(recap["programme"]["id"], self.maths_c.id)
        self.assertEqual(recap["programme"]["matiere"], "Mathématiques")
        self.assertEqual(recap["enonce_caracteres"], len("Résoudre dans R : x² - 5x + 6 = 0"))
        # L'énoncé n'est jamais renvoyé tel quel.
        self.assertNotIn("x²", reponse.content.decode())

    def test_chaque_format_image_est_accepte_par_son_contenu_reel(self):
        for nom, contenu, type_attendu in (
            ("a.jpg", JPEG, "image/jpeg"),
            ("b.png", PNG, "image/png"),
            ("c.webp", WEBP, "image/webp"),
        ):
            with self.subTest(nom=nom):
                reponse = self.deposer(fichiers=[fichier(nom, contenu)])
                self.assertEqual(reponse.status_code, 200, reponse.content)
                self.assertEqual(reponse.json()["recapitulatif"]["fichiers"][0]["type"], type_attendu)

    def test_le_type_reel_prime_sur_le_nom_et_le_type_declare(self):
        reponse = self.deposer(fichiers=[fichier("photo.txt", PNG, "text/plain")])
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(reponse.json()["recapitulatif"]["fichiers"][0]["type"], "image/png")

    def test_six_images_sont_acceptees(self):
        reponse = self.deposer(fichiers=[image(i) for i in range(NB_MAX_IMAGES)])
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(reponse.json()["recapitulatif"]["nb_fichiers"], NB_MAX_IMAGES)

    def test_pdf_seul_est_accepte(self):
        reponse = self.deposer(fichiers=[fichier("devoir.pdf", PDF, "application/pdf")])
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(reponse.json()["recapitulatif"]["fichiers"][0]["type"], "application/pdf")

    def test_fichier_et_enonce_ensemble(self):
        reponse = self.deposer(fichiers=[image()], enonce="Question 2 seulement.")
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(reponse.json()["recapitulatif"]["nb_fichiers"], 1)

    def test_taille_exactement_a_la_limite_est_acceptee(self):
        gros = JPEG + b"\x00" * (TAILLE_MAX_FICHIER_OCTETS - len(JPEG))
        self.assertEqual(len(gros), TAILLE_MAX_FICHIER_OCTETS)
        reponse = self.deposer(fichiers=[fichier("limite.jpg", gros)])
        self.assertEqual(reponse.status_code, 200, reponse.content)

    def test_enonce_de_4000_caracteres_est_accepte(self):
        reponse = self.deposer(enonce="a" * LONGUEUR_MAX_ENONCE)
        self.assertEqual(reponse.status_code, 200, reponse.content)

    def test_physique_est_accessible_comme_les_autres_matieres(self):
        reponse = self.deposer(programme=self.physique_c.id, enonce="Un solide glisse…")
        self.assertEqual(reponse.status_code, 200, reponse.content)

    # --- Fichiers invalides ------------------------------------------------

    def test_fichier_trop_volumineux_est_refuse(self):
        gros = JPEG + b"\x00" * (TAILLE_MAX_FICHIER_OCTETS + 1 - len(JPEG))
        reponse = self.deposer(fichiers=[fichier("enorme.jpg", gros, "image/jpeg")])
        self.assertEqual(reponse.status_code, 400)
        message = self.messages(reponse, "fichiers")
        self.assertIn("enorme.jpg", message)
        self.assertIn("trop volumineux", message)
        self.assertIn("10 Mo maximum", message)

    def test_type_incorrect_est_refuse(self):
        for nom, contenu in (
            ("notes.txt", b"juste du texte"),
            ("script.exe", b"MZ\x90\x00" + b"\x00" * 32),
            ("anim.gif", b"GIF89a" + b"\x00" * 32),
        ):
            with self.subTest(nom=nom):
                reponse = self.deposer(fichiers=[fichier(nom, contenu, "image/png")])
                self.assertEqual(reponse.status_code, 400)
                self.assertIn("n'est pas accepté", self.messages(reponse, "fichiers"))

    def test_faux_pdf_et_fausse_image_sont_refuses_malgre_leur_nom(self):
        reponse = self.deposer(fichiers=[fichier("faux.pdf", b"ceci n'est pas un pdf", "application/pdf")])
        self.assertEqual(reponse.status_code, 400)
        reponse = self.deposer(fichiers=[fichier("faux.jpg", b"<html>pirate</html>", "image/jpeg")])
        self.assertEqual(reponse.status_code, 400)

    def test_fichier_vide_est_refuse(self):
        reponse = self.deposer(fichiers=[fichier("vide.png", b"")])
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("est vide", self.messages(reponse, "fichiers"))

    def test_trop_de_photos_est_refuse(self):
        reponse = self.deposer(fichiers=[image(i) for i in range(NB_MAX_IMAGES + 1)])
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("6 fichiers maximum", self.messages(reponse, "fichiers"))

    def test_melange_pdf_et_images_est_refuse(self):
        reponse = self.deposer(fichiers=[image(), fichier("devoir.pdf", PDF)])
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("ne peut pas être envoyé avec des images", self.messages(reponse, "fichiers"))

    def test_deux_pdf_sont_refuses(self):
        reponse = self.deposer(fichiers=[fichier("a.pdf", PDF), fichier("b.pdf", PDF)])
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("Un seul PDF", self.messages(reponse, "fichiers"))

    def test_tous_les_fichiers_invalides_sont_signales(self):
        reponse = self.deposer(fichiers=[fichier("a.txt", b"x"), fichier("b.txt", b"y")])
        self.assertEqual(reponse.status_code, 400)
        message = self.messages(reponse, "fichiers")
        self.assertIn("a.txt", message)
        self.assertIn("b.txt", message)

    # --- Corps incomplet ---------------------------------------------------

    def test_ni_fichier_ni_enonce_est_refuse(self):
        for enonce in (None, "", "    \n  "):
            with self.subTest(enonce=enonce):
                reponse = self.deposer(enonce=enonce)
                self.assertEqual(reponse.status_code, 400)
                self.assertIn("Ajoute une photo", self.messages(reponse, "non_field_errors"))

    def test_enonce_trop_long_est_refuse(self):
        reponse = self.deposer(enonce="a" * (LONGUEUR_MAX_ENONCE + 1))
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("4000 caractères", self.messages(reponse, "enonce"))

    def test_mode_absent_ou_inconnu_est_refuse(self):
        reponse = self.deposer(mode=None, enonce="Texte")
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("Choisis un mode", self.messages(reponse, "mode"))

        reponse = self.deposer(mode="triche", enonce="Texte")
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("Mode inconnu", self.messages(reponse, "mode"))

    def test_programme_absent_ou_illisible_est_refuse(self):
        reponse = self.deposer(programme=None, enonce="Texte")
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("Indique le programme", self.messages(reponse, "programme"))

        reponse = self.deposer(programme="abc", enonce="Texte")
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("Programme invalide", self.messages(reponse, "programme"))

    def test_corps_json_est_refuse(self):
        reponse = self.client.post(URL, {"programme": self.maths_c.id, "mode": "correction", "enonce": "x"}, format="json")
        self.assertEqual(reponse.status_code, 415)

    # --- Accès au programme et authentification ---------------------------

    def test_programme_dune_autre_classe_donne_404(self):
        reponse = self.deposer(programme=self.maths_d.id, enonce="Texte")
        self.assertEqual(reponse.status_code, 404)

    def test_programme_inexistant_et_programme_etranger_sont_indiscernables(self):
        etranger = self.deposer(programme=self.maths_d.id, enonce="Texte")
        inexistant = self.deposer(programme=999999, enonce="Texte")
        self.assertEqual(etranger.status_code, 404)
        self.assertEqual(inexistant.status_code, 404)
        self.assertEqual(etranger.json(), inexistant.json())

    def test_programme_inaccessible_prime_sur_les_erreurs_de_fichier(self):
        reponse = self.deposer(programme=self.maths_d.id, fichiers=[fichier("x.txt", b"x")])
        self.assertEqual(reponse.status_code, 404)

    def test_matiere_hors_perimetre_est_refusee(self):
        reponse = self.deposer(programme=self.histoire_c.id, enonce="Texte")
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("pas disponible pour cette matière", self.messages(reponse, "programme"))

    def test_non_authentifie_donne_401(self):
        reponse = APIClient().post(URL, {"programme": self.maths_c.id, "mode": "correction", "enonce": "x"}, format="multipart")
        self.assertEqual(reponse.status_code, 401)

    def test_eleve_non_actif_donne_403(self):
        client = APIClient()
        client.force_authenticate(self.eleve_attente)
        reponse = client.post(URL, {"programme": self.maths_c.id, "mode": "correction", "enonce": "x"}, format="multipart")
        self.assertEqual(reponse.status_code, 403)

    def test_enseignant_donne_403(self):
        client = APIClient()
        client.force_authenticate(self.enseignant)
        reponse = client.post(URL, {"programme": self.maths_c.id, "mode": "correction", "enonce": "x"}, format="multipart")
        self.assertEqual(reponse.status_code, 403)

    def test_seule_la_methode_post_est_acceptee(self):
        self.assertEqual(self.client.get(URL).status_code, 405)

    # --- Rien n'est enregistré ni transmis --------------------------------

    def test_aucun_fichier_ecrit_et_aucun_appel_ia_ni_reseau(self):
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media), \
                mock.patch("programme.ia.fournisseurs.appeler_ia") as appeler_ia, \
                mock.patch("requests.post") as requests_post, \
                mock.patch("requests.get") as requests_get:
            reponse = self.deposer(fichiers=[image(1), image(2)], enonce="Avec deux pages.")

            self.assertEqual(reponse.status_code, 200, reponse.content)
            self.assertEqual(os.listdir(media), [])
            appeler_ia.assert_not_called()
            requests_post.assert_not_called()
            requests_get.assert_not_called()
