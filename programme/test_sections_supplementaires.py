"""
Sections facultatives « Simuler pour comprendre » et « Pour aller plus loin » :
champs vides par défaut, écriture indépendante (API admin), exposition élève
conditionnée au verrou premium, préservation des données existantes.
"""

from datetime import timedelta

from django.db import connection
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from comptes.models import User

from .models import Chapitre, Cycle, Lecon, Matiere, Niveau, Notion, Programme, Serie, Theme

SIMULER = "Fais varier $a$ :\n\n```courbe\nf(x) = a*x^2\n```"
PLUS_LOIN = "## Aller plus loin\n\n$$\\int_0^1 x\\,dx = \\tfrac12$$\n\n| a | b |\n|---|---|\n| 1 | 2 |"
COURS = "## Cours existant\n\n" + "Texte du cours. " * 400


class SectionsSupplementairesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cycle = Cycle.objects.create(nom="Second cycle", ordre=2)
        tle = Niveau.objects.create(cycle=cycle, nom="Terminale", ordre=7)
        serie = Serie.objects.create(niveau=tle, nom="C")
        programme = Programme.objects.create(matiere=Matiere.objects.create(nom="Mathématiques"), niveau=tle, serie=serie)
        theme = Theme.objects.create(programme=programme, titre="Analyse")
        chapitre = Chapitre.objects.create(theme=theme, titre="Fonctions")
        cls.notion = Notion.objects.create(chapitre=chapitre, titre="Parabole")
        cls.notion2 = Notion.objects.create(chapitre=chapitre, titre="Droite")
        cls.admin = User.objects.create_user(
            "+22790000051", password="Motdepasse-2026", prenom="A", nom="D", role=User.Role.ADMIN, statut=User.Statut.ACTIF,
        )
        kw = dict(password="Motdepasse-2026", prenom="E", nom="L", role=User.Role.ELEVE, statut=User.Statut.ACTIF, niveau=tle, serie=serie)
        cls.gratuit_eleve = User.objects.create_user("+22790000052", **kw)
        cls.abonne = User.objects.create_user("+22790000053", abonnement_actif_jusqu_au=timezone.localdate() + timedelta(days=10), **kw)

    def _lecon(self, notion=None, **extra):
        params = dict(notion=notion or self.notion, titre="Parabole", statut=Lecon.Statut.PUBLIE, est_gratuit=False, cours_redige=COURS)
        params.update(extra)
        return Lecon.objects.create(**params)

    def _admin(self):
        c = APIClient()
        c.force_authenticate(self.admin)
        return c

    def _eleve(self, user, lecon):
        c = APIClient()
        c.force_authenticate(user)
        return c.get(f"/api/eleve/lecons/{lecon.id}/")

    # 1. Leçon existante : les deux champs sont vides.
    def test_lecon_existante_champs_vides_par_defaut(self):
        lecon = self._lecon()
        lecon.refresh_from_db()
        self.assertEqual(lecon.simuler_pour_comprendre, "")
        self.assertEqual(lecon.pour_aller_plus_loin, "")
        data = self._admin().get(f"/api/admin/lecons/{lecon.id}/").json()
        self.assertEqual(data["simuler_pour_comprendre"], "")
        self.assertEqual(data["pour_aller_plus_loin"], "")

    # 2. Enregistrement du champ 1 seul.
    def test_enregistrement_simuler_seul(self):
        lecon = self._lecon(a_retenir="Retenir")
        r = self._admin().patch(f"/api/admin/lecons/{lecon.id}/", {"simuler_pour_comprendre": SIMULER}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        lecon.refresh_from_db()
        self.assertEqual(lecon.simuler_pour_comprendre, SIMULER)
        self.assertEqual(lecon.pour_aller_plus_loin, "")

    # 3. Enregistrement du champ 2 seul.
    def test_enregistrement_plus_loin_seul(self):
        lecon = self._lecon()
        r = self._admin().patch(f"/api/admin/lecons/{lecon.id}/", {"pour_aller_plus_loin": PLUS_LOIN}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        lecon.refresh_from_db()
        self.assertEqual(lecon.pour_aller_plus_loin, PLUS_LOIN)
        self.assertEqual(lecon.simuler_pour_comprendre, "")

    # 4. Enregistrement des deux.
    def test_enregistrement_des_deux(self):
        lecon = self._lecon()
        r = self._admin().patch(
            f"/api/admin/lecons/{lecon.id}/",
            {"simuler_pour_comprendre": SIMULER, "pour_aller_plus_loin": PLUS_LOIN}, format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        data = self._admin().get(f"/api/admin/lecons/{lecon.id}/").json()
        self.assertEqual((data["simuler_pour_comprendre"], data["pour_aller_plus_loin"]), (SIMULER, PLUS_LOIN))

    # 5. Création sans les champs : acceptée, vides.
    def test_creation_sans_les_champs(self):
        r = self._admin().post("/api/admin/lecons/", {"notion": self.notion2.id, "titre": "Droite"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        lecon = Lecon.objects.get(notion=self.notion2)
        self.assertEqual((lecon.simuler_pour_comprendre, lecon.pour_aller_plus_loin), ("", ""))

    # 6. Exposition élève abonné + champs vidés ensuite.
    def test_eleve_abonne_recoit_les_sections_puis_vides(self):
        lecon = self._lecon(simuler_pour_comprendre=SIMULER, pour_aller_plus_loin=PLUS_LOIN)
        data = self._eleve(self.abonne, lecon).json()
        self.assertFalse(data["verrouille"])
        self.assertEqual((data["simuler_pour_comprendre"], data["pour_aller_plus_loin"]), (SIMULER, PLUS_LOIN))
        self._admin().patch(f"/api/admin/lecons/{lecon.id}/", {"simuler_pour_comprendre": "", "pour_aller_plus_loin": ""}, format="json")
        data = self._eleve(self.abonne, lecon).json()
        self.assertEqual((data["simuler_pour_comprendre"], data["pour_aller_plus_loin"]), ("", ""))

    # 7. Protection premium : jamais transmis à un non-abonné sur leçon payante.
    def test_premium_non_abonne_ne_recoit_rien(self):
        lecon = self._lecon(simuler_pour_comprendre=SIMULER, pour_aller_plus_loin=PLUS_LOIN)
        r = self._eleve(self.gratuit_eleve, lecon)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["verrouille"])
        self.assertEqual((data["simuler_pour_comprendre"], data["pour_aller_plus_loin"]), ("", ""))
        self.assertNotIn("aller plus loin", r.content.decode().lower())
        self.assertNotIn("a*x^2", r.content.decode())

    # 8. Leçon gratuite : visible pour un non-abonné.
    def test_lecon_gratuite_visible_sans_abonnement(self):
        lecon = self._lecon(est_gratuit=True, simuler_pour_comprendre=SIMULER)
        data = self._eleve(self.gratuit_eleve, lecon).json()
        self.assertFalse(data["verrouille"])
        self.assertEqual(data["simuler_pour_comprendre"], SIMULER)

    # 9. Préservation : modifier une section ne touche à aucun autre contenu.
    def test_modification_preserve_les_donnees_existantes(self):
        lecon = self._lecon(
            histoire="H", demonstrations="D", a_retenir="R", sujet_examen="S",
            pour_aller_plus_loin=PLUS_LOIN,
        )
        r = self._admin().patch(f"/api/admin/lecons/{lecon.id}/", {"simuler_pour_comprendre": SIMULER}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        lecon.refresh_from_db()
        self.assertEqual(
            (lecon.titre, lecon.histoire, lecon.cours_redige, lecon.demonstrations, lecon.a_retenir, lecon.sujet_examen, lecon.pour_aller_plus_loin),
            ("Parabole", "H", COURS, "D", "R", "S", PLUS_LOIN),
        )
        # Et modifier un autre champ ne touche pas aux deux sections.
        self._admin().patch(f"/api/admin/lecons/{lecon.id}/", {"a_retenir": "R2"}, format="json")
        lecon.refresh_from_db()
        self.assertEqual((lecon.simuler_pour_comprendre, lecon.pour_aller_plus_loin, lecon.a_retenir), (SIMULER, PLUS_LOIN, "R2"))


class CompatibiliteTransitionTests(TestCase):
    """Transition de déploiement / rollback : l'ANCIEN backend ignore les deux
    colonnes. Leur DEFAULT '' doit rester PERSISTANT en base, sinon la création
    d'une leçon par l'ancien code violerait le NOT NULL."""

    COLONNES = ("simuler_pour_comprendre", "pour_aller_plus_loin")

    def test_le_default_de_base_est_persistant(self):
        with connection.cursor() as c:
            c.execute(
                "SELECT column_name, column_default, is_nullable FROM information_schema.columns "
                "WHERE table_name = 'programme_lecon' AND column_name IN %s",
                [self.COLONNES],
            )
            lignes = {nom: (defaut, nul) for nom, defaut, nul in c.fetchall()}
        self.assertEqual(set(lignes), set(self.COLONNES))
        for nom in self.COLONNES:
            self.assertIn("''", lignes[nom][0] or "", nom)
            self.assertEqual(lignes[nom][1], "NO")

    def test_insertion_par_l_ancien_backend_sans_les_deux_colonnes(self):
        cycle = Cycle.objects.create(nom="C", ordre=1)
        niveau = Niveau.objects.create(cycle=cycle, nom="N", ordre=1)
        serie = Serie.objects.create(niveau=niveau, nom="S")
        programme = Programme.objects.create(matiere=Matiere.objects.create(nom="M"), niveau=niveau, serie=serie)
        chapitre = Chapitre.objects.create(theme=Theme.objects.create(programme=programme, titre="T"), titre="Ch")
        notion = Notion.objects.create(chapitre=chapitre, titre="No")
        maintenant = timezone.now()
        # INSERT tel que l'ancien code le ferait : aucune mention des deux colonnes.
        with connection.cursor() as c:
            c.execute(
                "INSERT INTO programme_lecon (notion_id, titre, histoire, objectifs_pedagogiques, prerequis_texte, "
                "cours_redige, demonstrations, a_retenir, sujet_examen, est_gratuit, statut, cree_le, modifie_le) "
                "VALUES (%s, 'Ancienne', '', '', '', 'cours', '', '', '', false, 'brouillon', %s, %s)",
                [notion.id, maintenant, maintenant],
            )
        lecon = Lecon.objects.get(notion=notion)
        self.assertEqual((lecon.simuler_pour_comprendre, lecon.pour_aller_plus_loin), ("", ""))
