web: gunicorn --chdir app "main:app" --bind 0.0.0.0:$PORT --workers 2 --threads 2 --timeout 120 --log-level debug
worker: celery -A app.tasks worker --loglevel=info
beat: celery -A app.tasks beat --loglevel=info
