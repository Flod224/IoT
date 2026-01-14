#!/bin/bash
# Script de génération de certificats SSL auto-signés pour SmartIGLab
# Usage local (réseau privé)

echo "=== Génération certificat SSL pour SmartIGLab ==="
echo ""

# Créer dossier ssl si inexistant
mkdir -p ssl

# Générer clé privée et certificat (valide 365 jours)
openssl req -x509 -newkey rsa:4096 -nodes \
  -out ssl/cert.pem \
  -keyout ssl/key.pem \
  -days 365 \
  -subj "/C=BE/ST=Mons/L=Liege/O=SmartIGLab/CN=smartiglab.local"

echo ""
echo "✓ Certificats générés dans backend/ssl/"
echo ""
echo "Fichiers créés:"
echo "  - ssl/cert.pem  (certificat public)"
echo "  - ssl/key.pem   (clé privée)"
echo ""
echo " Important:"
echo "  - Certificat auto-signé = avertissement navigateur (normal)"
echo "  - Cliquer 'Avancé' puis 'Accepter le risque' dans le navigateur"
echo "  - Valide uniquement pour votre réseau local"
echo ""
