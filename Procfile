release: python manage.py migrate --noinput
web: gunicorn config.wsgi --workers ${WEB_CONCURRENCY:-2} --timeout 55 --graceful-timeout 25 --max-requests 1000 --max-requests-jitter 100
worker: python manage.py traiter_taches_ia
