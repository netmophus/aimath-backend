"""Renseigne ou affiche les paramètres de communication (tarif, plafond, lien WhatsApp).

Mêmes règles de validation que l'écran /admin/communications (ParametresSerializer) ; les valeurs sont enregistrées en
base et relues par le backend à chaque calcul et avant chaque envoi. Aucune valeur n'est écrite dans le code.
  python manage.py configurer_communications                              (lecture seule)
  python manage.py configurer_communications --tarif <FCFA> --plafond <FCFA>   (écriture)
Cette commande n'active rien : les envois restent commandés par COMMUNICATIONS_SMS_ACTIVES et le worker."""

from django.core.management.base import BaseCommand, CommandError

from communications import services
from communications.models import ParametresCommunication
from communications.serializers import ParametresSerializer


class Command(BaseCommand):
    help = "Affiche ou modifie le tarif d'un segment SMS, le plafond mensuel et le lien du groupe WhatsApp."

    def add_arguments(self, parser):
        parser.add_argument("--tarif", help="Coût d'un segment SMS en FCFA (strictement positif).")
        parser.add_argument("--plafond", help="Plafond mensuel de dépense SMS en FCFA (0 = envois bloqués).")
        parser.add_argument("--lien", help="Lien d'invitation du groupe WhatsApp.")

    def handle(self, *args, **options):
        donnees = {}
        if options["tarif"] is not None:
            donnees["cout_segment_fcfa"] = options["tarif"].replace(",", ".")
        if options["plafond"] is not None:
            donnees["plafond_mensuel_fcfa"] = options["plafond"]
        if options["lien"] is not None:
            donnees["lien_whatsapp"] = options["lien"]

        if donnees:
            ser = ParametresSerializer(data=donnees)
            if not ser.is_valid():
                raise CommandError(f"Valeurs refusées : {ser.errors}")
            d = ser.validated_data
            p = ParametresCommunication.charger()
            if "lien_whatsapp" in d:
                try:
                    p.lien_whatsapp = services.valider_lien_whatsapp(d["lien_whatsapp"])
                except services.ErreurMetier as e:
                    raise CommandError(e.message)
            if "plafond_mensuel_fcfa" in d:
                p.plafond_mensuel_fcfa = d["plafond_mensuel_fcfa"]
            if "cout_segment_fcfa" in d:
                p.cout_segment_fcfa = d["cout_segment_fcfa"]
            p.save()
            self.stdout.write("Paramètres enregistrés.")

        p = ParametresCommunication.objects.filter(pk=1).first()   # lecture seule : ne crée pas la ligne
        if p is None:
            self.stdout.write("Aucun paramètre enregistré : tarif inconnu, plafond 0 (aucun envoi possible).")
            return
        self.stdout.write(f"Tarif d'un segment : {p.cout_segment_fcfa if p.cout_segment_fcfa is not None else 'inconnu'} FCFA")
        self.stdout.write(f"Plafond mensuel : {p.plafond_mensuel_fcfa} FCFA")
        self.stdout.write(f"Lien WhatsApp : {'défini' if p.lien_whatsapp else 'non défini'}")
        self.stdout.write(f"Dépense du mois (estimée) : {services.depense_mois()} FCFA")
