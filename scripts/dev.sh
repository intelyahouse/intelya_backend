#!/bin/bash
echo "🚀 Lancement INTELYA HAVEN en développement..."
source venv/bin/activate
export DJANGO_ENV=development

# Lancer les migrations
python manage.py migrate

# Lancer le serveur avec Daphne (WebSocket support)
daphne -b 0.0.0.0 -p 8000 intelya.asgi:application
