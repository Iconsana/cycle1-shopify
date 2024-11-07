# Procfile
web: gunicorn "app:app" --bind 0.0.0.0:$PORT --workers 2 --threads 2 --timeout 120 --log-level info
worker: celery -A app.tasks worker --loglevel=info --concurrency=2 --max-tasks-per-child=100
beat: celery -A app.tasks beat --loglevel=info
