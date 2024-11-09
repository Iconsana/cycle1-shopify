web: gunicorn "cycle1-shopify.app:app" --bind 0.0.0.0:$PORT --workers 2 --threads 2 --timeout 120 --log-level debug
worker: celery -A cycle1-shopify.app.tasks worker --loglevel=info
beat: celery -A cycle1-shopify.app.tasks beat --loglevel=info
