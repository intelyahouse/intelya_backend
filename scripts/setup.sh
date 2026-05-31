#!/bin/bash
# INTELYA HAVEN - Script d'installation

echo "🚀 Installation INTELYA HAVEN Backend..."

# 1. Vérifier Python
python3 --version || { echo "Python3 requis!"; exit 1; }

# 2. Créer l'environnement virtuel
echo "📦 Création de l'environnement virtuel..."
python3 -m venv venv
source venv/bin/activate

# 3. Mettre à jour pip
pip install --upgrade pip

# 4. Installer les dépendances
echo "📥 Installation des packages..."
pip install -r requirements.txt

# 5. Copier le .env
if [ ! -f .env ]; then
    cp .env.example .env
    echo "⚠️  Fichier .env créé. REMPLIS les valeurs avant de continuer!"
fi

echo "✅ Installation terminée!"
echo ""
echo "Prochaines étapes:"
echo "1. Remplis le fichier .env avec tes vraies valeurs"
echo "2. Lance: docker-compose up -d db redis"
echo "3. Lance: python manage.py migrate"
echo "4. Lance: python manage.py createsuperuser"
echo "5. Lance: python manage.py runserver"
