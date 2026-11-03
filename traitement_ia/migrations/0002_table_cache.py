from django.core.management import call_command
from django.db import migrations


def creer_table_cache(apps, schema_editor):
    """Crée la table du cache partagé (settings.CACHES['default'], DatabaseCache). Idempotent : ne touche pas une table
    existante. Fait ici pour que la phase `release` de Heroku (migrate) suffise, sans commande supplémentaire."""
    call_command("createcachetable", database=schema_editor.connection.alias, verbosity=0)


class Migration(migrations.Migration):
    dependencies = [("traitement_ia", "0001_initial")]
    operations = [migrations.RunPython(creer_table_cache, migrations.RunPython.noop)]
