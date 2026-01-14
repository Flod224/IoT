#!/bin/bash
# Script de démarrage SmartIGLab avec HTTPS

echo " Démarrage SmartIGLab Backend (HTTPS)..."
echo ""
echo "Source Hyperplanning:"
echo "  1) JSON (schedule_mock.json) - Démo"
echo "  2) ICS (Edt_Ho_IGLab.ics) - Calendrier réel"
echo ""
read -p "Choix [1-2]: " choice

case $choice in
  2)
    echo " Mode ICS"
    export HYPERPLANNING_USE_ICS=True
    ;;
  *)
    echo " Mode JSON"
    export HYPERPLANNING_USE_ICS=False
    ;;
esac

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
