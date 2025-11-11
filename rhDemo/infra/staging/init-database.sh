#!/bin/bash

#═══════════════════════════════════════════════════════════════
# Script d'initialisation de la base de données RHDemo
# Utilise pgddl.sql pour créer le schéma et insérer les données
#
# Usage:
#   ./init-database.sh              # Mode interactif (demande confirmation)
#   ./init-database.sh --force      # Mode CI/CD (pas de confirmation)
#═══════════════════════════════════════════════════════════════

set -e  # Arrêter en cas d'erreur

# Mode force pour CI/CD
FORCE_MODE=false
if [[ "$1" == "--force" || "$1" == "-f" ]]; then
    FORCE_MODE=true
fi

# Couleurs pour l'affichage (désactivées en mode force)
if [ "$FORCE_MODE" = true ]; then
    GREEN=''
    BLUE=''
    YELLOW=''
    RED=''
    NC=''
else
    GREEN='\033[0;32m'
    BLUE='\033[0;34m'
    YELLOW='\033[1;33m'
    RED='\033[0;31m'
    NC='\033[0m' # No Color
fi

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_FILE="${SCRIPT_DIR}/../../pgddl.sql"
DB_CONTAINER="rhdemo-staging-db"
DB_NAME="rhdemo"
DB_USER="rhdemo"

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Initialisation de la base de données RHDemo${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Vérifier que le fichier SQL existe
if [ ! -f "$SQL_FILE" ]; then
    echo -e "${RED}❌ Erreur: Le fichier SQL n'existe pas: $SQL_FILE${NC}"
    exit 1
fi

# Vérifier que le container PostgreSQL est en cours d'exécution
if ! sudo docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
    echo -e "${RED}❌ Erreur: Le container $DB_CONTAINER n'est pas en cours d'exécution${NC}"
    echo -e "${YELLOW}   Démarrez d'abord l'environnement: sudo docker compose up -d${NC}"
    exit 1
fi

echo -e "${BLUE}→ Vérification de l'accessibilité de PostgreSQL...${NC}"
RETRIES=0
MAX_RETRIES=30
until sudo docker exec "$DB_CONTAINER" pg_isready -U "$DB_USER" -d "$DB_NAME" > /dev/null 2>&1; do
    RETRIES=$((RETRIES + 1))
    if [ $RETRIES -ge $MAX_RETRIES ]; then
        echo -e "${RED}❌ PostgreSQL n'est pas accessible après $MAX_RETRIES tentatives${NC}"
        exit 1
    fi
    echo -e "${YELLOW}   Attente de PostgreSQL... ($RETRIES/$MAX_RETRIES)${NC}"
    sleep 1
done
echo -e "${GREEN}✓ PostgreSQL est accessible${NC}"
echo ""

# Demander confirmation avant de réinitialiser (sauf en mode force)
if [ "$FORCE_MODE" = false ]; then
    echo -e "${YELLOW}⚠️  ATTENTION: Cette opération va SUPPRIMER toutes les données existantes !${NC}"
    echo -e "${YELLOW}   Les tables suivantes seront supprimées puis recréées:${NC}"
    echo -e "${YELLOW}   - employes (avec tous les enregistrements)${NC}"
    echo ""
    read -p "Voulez-vous continuer ? (oui/non) " -r
    echo ""
    if [[ ! $REPLY =~ ^[Oo][Uu][Ii]$ ]]; then
        echo -e "${BLUE}ℹ️  Opération annulée${NC}"
        exit 0
    fi
else
    echo -e "${BLUE}ℹ️  Mode force activé - Suppression automatique des données${NC}"
    echo ""
fi

# Copier le fichier SQL dans le container
echo -e "${BLUE}→ Copie du fichier SQL dans le container...${NC}"
sudo docker cp "$SQL_FILE" "${DB_CONTAINER}:/tmp/init.sql"
echo -e "${GREEN}✓ Fichier copié${NC}"
echo ""

# Exécuter le script SQL
echo -e "${BLUE}→ Exécution du script SQL...${NC}"
echo -e "${BLUE}   - Suppression de la table 'employes'${NC}"
echo -e "${BLUE}   - Création de la table avec index${NC}"
echo -e "${BLUE}   - Insertion des données (300+ employés)${NC}"
echo ""

if sudo docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -f /tmp/init.sql > /tmp/init-db.log 2>&1; then
    echo -e "${GREEN}✓ Script SQL exécuté avec succès${NC}"
else
    echo -e "${RED}❌ Erreur lors de l'exécution du script SQL${NC}"
    echo -e "${RED}   Voir les détails dans /tmp/init-db.log${NC}"
    cat /tmp/init-db.log
    exit 1
fi
echo ""

# Vérifier le nombre d'employés insérés
echo -e "${BLUE}→ Vérification des données insérées...${NC}"
EMPLOYEE_COUNT=$(sudo docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM employes;" | xargs)
echo -e "${GREEN}✓ Nombre d'employés dans la base: ${EMPLOYEE_COUNT}${NC}"
echo ""

# Afficher les index créés
echo -e "${BLUE}→ Index créés sur la table 'employes':${NC}"
sudo docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "
SELECT 
    indexname AS \"Index\",
    indexdef AS \"Définition\"
FROM pg_indexes 
WHERE tablename = 'employes'
ORDER BY indexname;
" | grep -E "Index|idx_|---" || true
echo ""

# Nettoyage
sudo docker exec "$DB_CONTAINER" rm -f /tmp/init.sql
rm -f /tmp/init-db.log

echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✅ Base de données initialisée avec succès !                ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}📊 Résumé:${NC}"
echo -e "${BLUE}   • Base de données: ${DB_NAME}${NC}"
echo -e "${BLUE}   • Nombre d'employés: ${EMPLOYEE_COUNT}${NC}"
echo -e "${BLUE}   • Index créés: 5 (mail unique, nom, prénom, nom+prénom, adresse)${NC}"
echo ""
echo -e "${BLUE}🔗 Connexion à la base:${NC}"
echo -e "${BLUE}   sudo docker exec -it ${DB_CONTAINER} psql -U ${DB_USER} -d ${DB_NAME}${NC}"
echo ""
echo -e "${BLUE}📋 Prochaines étapes:${NC}"
echo -e "${BLUE}   1. Redémarrer l'application si nécessaire:${NC}"
echo -e "${BLUE}      sudo docker compose restart rhdemo-app${NC}"
echo -e "${BLUE}   2. Tester l'accès: https://rhdemo.staging.local${NC}"
echo ""
