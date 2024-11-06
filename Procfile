web: gunicorn 'app.main:app' --bind 0.0.0.0:$PORT
worker: celery -A app.tasks worker --loglevel=info
