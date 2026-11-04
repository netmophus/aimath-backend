from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from django.test import TestCase

from aide import fichiers
from aide.models import DemandeAide
from budget_ia.tests.outils import creer_eleve, creer_programme_maths
from comptes.models import User
from programme.models import Chapitre, Lecon, Matiere, Notion, Programme, Theme

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 64
URL = "/api/eleve/aide/demandes/"


def lecon_de(programme, titre="Limites", statut=Lecon.Statut.PUBLIE):
    theme = Theme.objects.create(programme=programme, titre="T")
    chap = Chapitre.objects.create(theme=theme, titre="C")
    notion = Notion.objects.create(chapitre=chap, titre=titre)
    return Lecon.objects.create(notion=notion, titre=titre, statut=statut)


class Base(TestCase):
    def setUp(self):
        self.eleve, self.programme = creer_programme_maths()
        self.lecon = lecon_de(self.programme)
        self.api = APIClient()
        self.api.force_authenticate(self.eleve)
        self.n = 0

    def envoyer(self, api=None, **champs):
        self.n += 1
        corps = {"cle": f"cle-test-{self.n:04d}", "type": "question", "message": "Je ne comprends pas."}
        corps.update(champs)
        return (api or self.api).post(URL, corps, format="multipart")

    def admin(self):
        a = User.objects.create_user("+22790000001", password="Motdepasse-2026", prenom="A", nom="D",
                                     role=User.Role.ADMIN, statut=User.Statut.ACTIF)
        c = APIClient()
        c.force_authenticate(a)
        return c


class CreationTests(Base):
    def test_question(self):
        r = self.envoyer(programme=self.programme.id, lecon=self.lecon.id)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data["type"], r.data["statut"], r.data["a_reponse"]), ("question", "recue", False))
        self.assertEqual(r.data["matiere"]["nom"], "Mathématiques")
        self.assertEqual(r.data["lecon"]["id"], self.lecon.id)
        self.assertEqual(DemandeAide.objects.get().eleve, self.eleve)

    def test_erreur(self):
        r = self.envoyer(type="erreur", programme=self.programme.id)
        self.assertEqual((r.status_code, r.data["type"]), (201, "erreur"))

    def test_suggestion_sans_matiere(self):
        r = self.envoyer(type="suggestion", message="Ajoutez des vidéos.")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data["matiere"], r.data["lecon"]), (None, None))

    def test_type_inconnu_refuse(self):
        self.assertEqual(self.envoyer(type="autre").status_code, 400)

    def test_message_obligatoire(self):
        for vide in ("", "   \n  "):
            r = self.envoyer(message=vide)
            self.assertEqual(r.status_code, 400)
            self.assertIn("message", r.data)
        self.assertEqual(DemandeAide.objects.count(), 0)

    def test_message_trop_long(self):
        self.assertEqual(self.envoyer(message="a" * 1001).status_code, 400)
        self.assertEqual(self.envoyer(message="a" * 1000).status_code, 201)

    def test_lecon_verifiee(self):
        autre_matiere = Matiere.objects.create(nom="Physique")
        autre = Programme.objects.create(matiere=autre_matiere, niveau=self.programme.niveau, serie=self.programme.serie)
        lecon_autre = lecon_de(autre, "Forces")
        brouillon = lecon_de(self.programme, "Brouillon", Lecon.Statut.BROUILLON)
        # leçon d'une autre matière, leçon non publiée, leçon sans matière, leçon inexistante : toutes refusées
        for champs in ({"programme": self.programme.id, "lecon": lecon_autre.id},
                       {"programme": self.programme.id, "lecon": brouillon.id},
                       {"lecon": self.lecon.id},
                       {"programme": self.programme.id, "lecon": 999999}):
            r = self.envoyer(**champs)
            self.assertEqual(r.status_code, 400, champs)
            self.assertIn("lecon", r.data)

    def test_matiere_d_une_autre_classe_refusee(self):
        from programme.models import Niveau
        autre_niveau = Niveau.objects.create(cycle=self.programme.niveau.cycle, nom="Première", ordre=6)
        etrangere = Programme.objects.create(matiere=self.programme.matiere, niveau=autre_niveau)
        r = self.envoyer(programme=etrangere.id)
        self.assertEqual(r.status_code, 400)
        self.assertIn("programme", r.data)


class PieceJointeTests(Base):
    def fichier(self, octets, nom="photo.png", type_="image/png"):
        return SimpleUploadedFile(nom, octets, content_type=type_)

    def test_images_valides(self):
        for octets, type_ in ((PNG, "image/png"), (JPEG, "image/jpeg"), (WEBP, "image/webp")):
            r = self.envoyer(piece_jointe=self.fichier(octets, "x.bin", type_))
            self.assertEqual(r.status_code, 201, r.data)
            self.assertTrue(r.data["a_piece_jointe"])
            DemandeAide.objects.all().delete()

    def test_piece_jointe_lisible_par_son_proprietaire_seulement(self):
        r = self.envoyer(piece_jointe=self.fichier(PNG))
        url = f"{URL}{r.data['id']}/piece-jointe/"
        lecture = self.api.get(url)
        self.assertEqual((lecture.status_code, lecture["Content-Type"]), (200, "image/png"))
        self.assertEqual(lecture.content, PNG)
        self.assertEqual(lecture["Cache-Control"], "private, no-store")
        self.assertEqual(lecture["X-Content-Type-Options"], "nosniff")
        autre = APIClient()
        autre.force_authenticate(creer_eleve("+22790000066", niveau=self.programme.niveau, serie=self.programme.serie))
        self.assertEqual(autre.get(url).status_code, 404)
        self.assertEqual(APIClient().get(url).status_code, 401)
        self.assertEqual(self.admin().get(f"/api/admin/aide/demandes/{r.data['id']}/piece-jointe/").status_code, 200)

    def test_fichier_invalide_refuse(self):
        faux = [
            self.fichier(b"<script>alert(1)</script>", "x.png", "image/png"),     # contenu non image, nom image
            self.fichier(b"%PDF-1.4 ...", "x.pdf", "application/pdf"),
            self.fichier(PNG, "x.png", "image/jpeg"),                              # type annoncé différent du contenu
            self.fichier(b"GIF89a" + b"\x00" * 30, "x.gif", "image/gif"),
        ]
        for f in faux:
            r = self.envoyer(piece_jointe=f)
            self.assertEqual(r.status_code, 400)
            self.assertIn("piece_jointe", r.data)
        self.assertEqual(DemandeAide.objects.count(), 0)

    def test_fichier_trop_volumineux_refuse(self):
        gros = self.fichier(PNG + b"\x00" * fichiers.TAILLE_MAX)
        r = self.envoyer(piece_jointe=gros)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(str(r.data["piece_jointe"][0]), "Image trop lourde (5 Mo max).")
        self.assertEqual(DemandeAide.objects.count(), 0)


class ConsultationTests(Base):
    def test_liste_du_proprietaire_seulement(self):
        self.envoyer(message="Ma demande")
        autre = creer_eleve("+22790000066", niveau=self.programme.niveau, serie=self.programme.serie)
        c = APIClient()
        c.force_authenticate(autre)
        self.envoyer(api=c, message="Celle d'un autre")
        mes = self.api.get(URL)
        self.assertEqual([d["message"] for d in mes.data], ["Ma demande"])
        self.assertNotIn("eleve", mes.data[0])

    def test_demande_d_un_autre_eleve_refusee(self):
        autre = creer_eleve("+22790000066", niveau=self.programme.niveau, serie=self.programme.serie)
        c = APIClient()
        c.force_authenticate(autre)
        theirs = self.envoyer(api=c).data["id"]
        self.assertEqual(self.api.get(f"{URL}{theirs}/").status_code, 404)
        self.assertEqual(self.api.get(f"{URL}{theirs}/piece-jointe/").status_code, 404)

    def test_acces_anonyme_refuse(self):
        anonyme = APIClient()
        self.assertEqual(anonyme.get(URL).status_code, 401)
        self.assertEqual(anonyme.post(URL, {"type": "question", "message": "x", "cle": "abcdefgh"}).status_code, 401)
        self.assertEqual(anonyme.get("/api/admin/aide/demandes/").status_code, 401)

    def test_eleve_ne_peut_pas_utiliser_l_administration(self):
        d = self.envoyer().data["id"]
        self.assertEqual(self.api.get("/api/admin/aide/demandes/").status_code, 403)
        r = self.api.patch(f"/api/admin/aide/demandes/{d}/", {"statut": "traitee", "reponse": "pirate"}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(DemandeAide.objects.get().statut, "recue")

    def test_eleve_ne_peut_pas_forcer_statut_ni_reponse(self):
        r = self.envoyer(statut="traitee", reponse="Faux", reponse_par=1)
        self.assertEqual(r.status_code, 201)
        d = DemandeAide.objects.get()
        self.assertEqual((d.statut, d.reponse, d.reponse_par), ("recue", "", None))
        self.assertEqual(self.api.patch(f"{URL}{d.id}/", {"statut": "traitee"}, format="json").status_code, 405)

    def test_compte_non_eleve_actif_refuse(self):
        en_attente = creer_eleve("+22790000077")
        User.objects.filter(pk=en_attente.pk).update(statut=User.Statut.EN_ATTENTE)
        c = APIClient()
        c.force_authenticate(User.objects.get(pk=en_attente.pk))
        self.assertEqual(c.get(URL).status_code, 403)


class AdministrationTests(Base):
    def test_statut_reponse_et_lecture_par_l_eleve(self):
        d = self.envoyer(programme=self.programme.id).data["id"]
        adm = self.admin()
        liste = adm.get("/api/admin/aide/demandes/")
        self.assertEqual(liste.status_code, 200)
        self.assertEqual(liste.data["results"][0]["eleve"]["telephone"], self.eleve.telephone)

        r = adm.patch(f"/api/admin/aide/demandes/{d}/", {"statut": "en_cours"}, format="json")
        self.assertEqual((r.status_code, r.data["statut"], r.data["traitee_le"]), (200, "en_cours", None))
        r = adm.patch(f"/api/admin/aide/demandes/{d}/", {"reponse": "Voici l'explication.", "statut": "traitee"}, format="json")
        self.assertEqual((r.data["statut"], r.data["a_reponse"]), ("traitee", True))
        self.assertIsNotNone(r.data["traitee_le"])
        self.assertIsNotNone(r.data["reponse_le"])

        vue = self.api.get(f"{URL}{d}/")
        self.assertEqual((vue.data["reponse"], vue.data["statut"]), ("Voici l'explication.", "traitee"))
        self.assertNotIn("reponse_par", vue.data)

    def test_traitee_sans_reponse_et_reponse_ouvre_en_cours(self):
        adm = self.admin()
        d1 = self.envoyer().data["id"]
        r = adm.patch(f"/api/admin/aide/demandes/{d1}/", {"statut": "traitee"}, format="json")
        self.assertEqual((r.data["statut"], r.data["a_reponse"]), ("traitee", False))
        d2 = self.envoyer().data["id"]
        r = adm.patch(f"/api/admin/aide/demandes/{d2}/", {"reponse": "Bonjour"}, format="json")
        self.assertEqual(r.data["statut"], "en_cours")

    def test_statut_invalide_refuse(self):
        d = self.envoyer().data["id"]
        self.assertEqual(self.admin().patch(f"/api/admin/aide/demandes/{d}/", {"statut": "x"}, format="json").status_code, 400)

    def test_filtres_et_recherche(self):
        self.envoyer(type="erreur", message="Faute dans le cours")
        self.envoyer(type="suggestion", message="Plus de vidéos")
        d = self.envoyer(type="question", message="Une question").data["id"]
        adm = self.admin()
        adm.patch(f"/api/admin/aide/demandes/{d}/", {"statut": "traitee"}, format="json")
        total = lambda **p: adm.get("/api/admin/aide/demandes/", p).data["count"]
        self.assertEqual(total(), 3)
        self.assertEqual(total(type="erreur"), 1)
        self.assertEqual(total(statut="traitee"), 1)
        self.assertEqual(total(q="vidéos"), 1)
        self.assertEqual(total(type="erreur", q="vidéos"), 0)


class DoubleSoumissionTests(Base):
    def test_meme_cle_ne_cree_qu_une_demande(self):
        a = self.envoyer(cle="cle-identique-1")
        b = self.envoyer(cle="cle-identique-1")
        self.assertEqual((a.status_code, b.status_code), (201, 200))
        self.assertEqual(a.data["id"], b.data["id"])
        self.assertEqual(DemandeAide.objects.count(), 1)

    def test_cle_d_un_autre_eleve_ne_donne_pas_sa_demande(self):
        autre = creer_eleve("+22790000066", niveau=self.programme.niveau, serie=self.programme.serie)
        c = APIClient()
        c.force_authenticate(autre)
        a = self.envoyer(api=c, cle="cle-partagee-1", message="Privé")
        b = self.envoyer(cle="cle-partagee-1", message="Mienne")
        self.assertNotEqual(a.data["id"], b.data["id"])
        self.assertEqual(b.data["message"], "Mienne")

    def test_limite_par_minute(self):
        codes = [self.envoyer().status_code for _ in range(4)]
        self.assertEqual(codes, [201, 201, 201, 429])
        self.assertEqual(DemandeAide.objects.count(), 3)


class SurveillanceEtAccesTests(Base):
    def test_commande_espace_et_seuil(self):
        from io import StringIO
        from django.core.management import call_command
        from django.test import override_settings
        self.envoyer(piece_jointe=SimpleUploadedFile("a.png", PNG, content_type="image/png"))
        sortie = StringIO()
        call_command("espace_aide", stdout=sortie)
        self.assertIn("Pièces jointes : 1", sortie.getvalue())
        with override_settings(AIDE_ESPACE_ALERTE_MO=0):
            with self.assertRaises(SystemExit):
                call_command("espace_aide", stdout=StringIO(), stderr=StringIO())

    def test_pieces_jointes_refusees_aux_autres_roles(self):
        d = self.envoyer(piece_jointe=SimpleUploadedFile("a.png", PNG, content_type="image/png")).data["id"]
        url = f"/api/admin/aide/demandes/{d}/piece-jointe/"
        vendeur = User.objects.create_user("+22790000002", password="Motdepasse-2026", prenom="V", nom="D",
                                           role=User.Role.VENDEUR, statut=User.Statut.ACTIF)
        c = APIClient()
        c.force_authenticate(vendeur)
        self.assertEqual(c.get(url).status_code, 403)
        self.assertEqual(c.get("/api/admin/aide/demandes/").status_code, 403)
        self.assertEqual(APIClient().get(url).status_code, 401)
