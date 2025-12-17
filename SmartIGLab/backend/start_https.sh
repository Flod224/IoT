#!/bin/bash
# Script de démarrage SmartIGLab avec HTTPS

echo "🚀 Démarrage SmartIGLab Backend (HTTPS)..."
echo ""

# Vérifier certificats SSL
if [ ! -f "ssl/cert.pem" ] || [ ! -f "ssl/key.pem" ]; then
    echo "⚠️  Certificats SSL manquants!"
    echo "Génération automatique..."
    ./generate_ssl_cert.sh
fi

# Démarrer uvicorn avec SSL
echo "Démarrage serveur HTTPS sur port 8000..."
echo "Dashboard: https://<IP_RASPBERRY>:8000/"
echo ""

uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --ssl-keyfile=ssl/key.pem \
    --ssl-certfile=ssl/cert.pem \
    --reload
