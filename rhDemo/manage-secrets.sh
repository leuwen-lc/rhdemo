#!/bin/bash

##############################################################################
# Script de gestion des secrets SOPS pour RHDemo
# Usage: ./manage-secrets.sh [command] [options]
##############################################################################

set -e

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SECRETS_DIR="secrets"
AGE_KEY_FILE="${SOPS_AGE_KEY_FILE:-$HOME/.config/sops/age/keys.txt}"

##############################################################################
# Fonctions d'affichage
##############################################################################

print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}          ${GREEN}GESTION DES SECRETS SOPS - RHDemo${NC}              ${BLUE}║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}" >&2
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

##############################################################################
# Vérifications
##############################################################################

check_dependencies() {
    local missing=()
    
    if ! command -v sops &> /dev/null; then
        missing+=("sops")
    fi
    
    if ! command -v age &> /dev/null; then
        missing+=("age")
    fi
    
    if ! command -v yq &> /dev/null; then
        missing+=("yq")
    fi
    
    if [ ${#missing[@]} -ne 0 ]; then
        print_error "Dépendances manquantes: ${missing[*]}"
        echo ""
        echo "Installation requise:"
        echo "  - SOPS: https://github.com/mozilla/sops#download"
        echo "  - Age: https://github.com/FiloSottile/age#installation"
        echo "  - yq: https://github.com/mikefarah/yq#install"
        exit 1
    fi
}

check_age_key() {
    if [ ! -f "$AGE_KEY_FILE" ]; then
        print_error "Clé Age non trouvée: $AGE_KEY_FILE"
        echo ""
        echo "Créez une clé avec: $0 create-key"
        echo "Ou définissez SOPS_AGE_KEY_FILE vers votre clé existante"
        exit 1
    fi
    export SOPS_AGE_KEY_FILE="$AGE_KEY_FILE"
}

##############################################################################
# Commandes
##############################################################################

cmd_create_key() {
    print_info "Génération d'une nouvelle clé Age..."
    
    # Créer le répertoire si nécessaire
    mkdir -p "$(dirname "$AGE_KEY_FILE")"
    
    # Générer la clé
    age-keygen -o "$AGE_KEY_FILE"
    
    print_success "Clé générée: $AGE_KEY_FILE"
    echo ""
    print_warning "IMPORTANT: Sauvegardez cette clé de manière sécurisée!"
    print_warning "Sans cette clé, vous ne pourrez pas déchiffrer vos secrets."
    echo ""
    
    # Afficher le recipient
    local recipient=$(grep "public key:" "$AGE_KEY_FILE" | cut -d: -f2 | tr -d ' ')
    print_info "Votre recipient (clé publique):"
    echo -e "  ${GREEN}$recipient${NC}"
    echo ""
    print_info "Utilisez ce recipient pour chiffrer vos fichiers:"
    echo "  sops -e --age $recipient secrets-example.yml > secrets-staging.yml"
}

cmd_encrypt() {
    local input_file="${1:-secrets/secrets-example.yml}"
    local output_file="${2:-secrets/secrets-staging.yml}"
    
    if [ ! -f "$input_file" ]; then
        print_error "Fichier source non trouvé: $input_file"
        exit 1
    fi
    
    check_age_key
    
    print_info "Chiffrement de $input_file..."
    
    # Extraire le recipient depuis la clé
    local recipient=$(grep "public key:" "$AGE_KEY_FILE" | cut -d: -f2 | tr -d ' ')
    
    # Chiffrer
    sops -e --age "$recipient" "$input_file" > "$output_file"
    
    print_success "Fichier chiffré créé: $output_file"
    print_warning "Vous pouvez maintenant commiter ce fichier dans Git"
}

cmd_decrypt() {
    local input_file="${1:-secrets/secrets-staging.yml}"
    local output_file="${2:-secrets/secrets-staging-decrypted.yml}"
    
    if [ ! -f "$input_file" ]; then
        print_error "Fichier chiffré non trouvé: $input_file"
        exit 1
    fi
    
    check_age_key
    
    print_info "Déchiffrement de $input_file..."
    
    sops -d "$input_file" > "$output_file"
    
    print_success "Fichier déchiffré: $output_file"
    print_warning "NE COMMITTEZ PAS ce fichier dans Git!"
    print_warning "Supprimez-le après utilisation: rm $output_file"
}

cmd_edit() {
    local file="${1:-secrets/secrets-staging.yml}"
    
    if [ ! -f "$file" ]; then
        print_error "Fichier non trouvé: $file"
        exit 1
    fi
    
    check_age_key
    
    print_info "Édition de $file avec SOPS..."
    print_info "L'éditeur va s'ouvrir. Modifications seront rechiffrées automatiquement."
    
    sops "$file"
    
    print_success "Fichier modifié et rechiffré"
}

cmd_view() {
    local file="${1:-secrets/secrets-staging.yml}"
    
    if [ ! -f "$file" ]; then
        print_error "Fichier non trouvé: $file"
        exit 1
    fi
    
    check_age_key
    
    print_info "Contenu déchiffré de $file:"
    echo ""
    
    sops -d "$file"
}

cmd_extract() {
    local file="${1:-secrets/secrets-staging.yml}"
    
    if [ ! -f "$file" ]; then
        print_error "Fichier non trouvé: $file"
        exit 1
    fi
    
    check_age_key
    
    print_info "Extraction des variables d'environnement..."
    
    # Déchiffrer temporairement
    local temp_file=$(mktemp)
    sops -d "$file" > "$temp_file"
    
    # Créer le fichier env-vars.sh
    cat > "$SECRETS_DIR/env-vars.sh" << 'EOF'
#!/bin/bash
# Variables d'environnement générées depuis secrets SOPS
# NE PAS COMMITER CE FICHIER

EOF
    
    echo "export RHDEMO_DATASOURCE_PASSWORD_PG=\"$(yq eval '.rhdemo.datasource.password.pg' "$temp_file")\"" >> "$SECRETS_DIR/env-vars.sh"
    echo "export RHDEMO_DATASOURCE_PASSWORD_H2=\"$(yq eval '.rhdemo.datasource.password.h2' "$temp_file")\"" >> "$SECRETS_DIR/env-vars.sh"
    echo "export RHDEMO_CLIENT_REGISTRATION_KEYCLOAK_CLIENT_SECRET=\"$(yq eval '.rhdemo.client.registration.keycloak.client.secret' "$temp_file")\"" >> "$SECRETS_DIR/env-vars.sh"
    
    # Extraire les URLs de serveurs si elles existent
    if yq eval '.rhdemo.servers.staging' "$temp_file" > /dev/null 2>&1; then
        echo "export STAGING_SERVER=\"$(yq eval '.rhdemo.servers.staging' "$temp_file")\"" >> "$SECRETS_DIR/env-vars.sh"
    fi
    
    if yq eval '.rhdemo.servers.production' "$temp_file" > /dev/null 2>&1; then
        echo "export PROD_SERVER=\"$(yq eval '.rhdemo.servers.production' "$temp_file")\"" >> "$SECRETS_DIR/env-vars.sh"
    fi
    
    # Nettoyer
    rm -f "$temp_file"
    chmod 600 "$SECRETS_DIR/env-vars.sh"
    
    print_success "Fichier créé: $SECRETS_DIR/env-vars.sh"
    echo ""
    print_info "Utilisez: source $SECRETS_DIR/env-vars.sh"
    print_warning "Supprimez après utilisation: rm $SECRETS_DIR/env-vars.sh"
}

cmd_validate() {
    local file="${1:-secrets/secrets-staging.yml}"
    
    if [ ! -f "$file" ]; then
        print_error "Fichier non trouvé: $file"
        exit 1
    fi
    
    check_age_key
    
    print_info "Validation de $file..."
    
    # Tester le déchiffrement
    if ! sops -d "$file" > /dev/null 2>&1; then
        print_error "Impossible de déchiffrer le fichier"
        exit 1
    fi
    
    # Déchiffrer dans un fichier temporaire
    local temp_file=$(mktemp)
    sops -d "$file" > "$temp_file"
    
    # Valider la structure YAML
    if ! yq eval '.' "$temp_file" > /dev/null 2>&1; then
        print_error "Structure YAML invalide"
        rm -f "$temp_file"
        exit 1
    fi
    
    # Vérifier les champs requis
    local required_fields=(
        ".rhdemo.datasource.password.pg"
        ".rhdemo.datasource.password.h2"
        ".rhdemo.client.registration.keycloak.client.secret"
    )
    
    local missing=()
    for field in "${required_fields[@]}"; do
        if ! yq eval "$field" "$temp_file" > /dev/null 2>&1; then
            missing+=("$field")
        fi
    done
    
    rm -f "$temp_file"
    
    if [ ${#missing[@]} -ne 0 ]; then
        print_error "Champs requis manquants:"
        for field in "${missing[@]}"; do
            echo "  - $field"
        done
        exit 1
    fi
    
    print_success "Fichier valide ✓"
    print_success "Déchiffrement réussi ✓"
    print_success "Structure YAML valide ✓"
    print_success "Tous les champs requis présents ✓"
}

cmd_rotate() {
    local file="${1:-secrets/secrets-staging.yml}"
    
    if [ ! -f "$file" ]; then
        print_error "Fichier non trouvé: $file"
        exit 1
    fi
    
    check_age_key
    
    print_warning "Rotation de la clé Age..."
    print_info "Cette opération va:"
    echo "  1. Créer une nouvelle clé Age"
    echo "  2. Déchiffrer le fichier avec l'ancienne clé"
    echo "  3. Rechiffrer avec la nouvelle clé"
    echo ""
    read -p "Continuer? (y/N) " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Opération annulée"
        exit 0
    fi
    
    # Sauvegarder l'ancienne clé
    cp "$AGE_KEY_FILE" "$AGE_KEY_FILE.old"
    
    # Déchiffrer avec l'ancienne clé
    local temp_file=$(mktemp)
    sops -d "$file" > "$temp_file"
    
    # Générer nouvelle clé
    age-keygen -o "$AGE_KEY_FILE"
    local new_recipient=$(grep "public key:" "$AGE_KEY_FILE" | cut -d: -f2 | tr -d ' ')
    
    # Rechiffrer avec la nouvelle clé
    sops -e --age "$new_recipient" "$temp_file" > "$file"
    
    rm -f "$temp_file"
    
    print_success "Clé rotée avec succès"
    print_info "Nouvelle clé: $AGE_KEY_FILE"
    print_info "Ancienne clé sauvegardée: $AGE_KEY_FILE.old"
    print_info "Nouveau recipient: $new_recipient"
    print_warning "Mettez à jour le credential Jenkins avec la nouvelle clé!"
}

cmd_help() {
    print_header
    cat << EOF
Usage: $0 <command> [options]

Commandes disponibles:

  create-key                 Générer une nouvelle clé Age
  encrypt [input] [output]   Chiffrer un fichier
  decrypt [input] [output]   Déchiffrer un fichier
  edit [file]                Éditer un fichier chiffré
  view [file]                Afficher le contenu déchiffré
  extract [file]             Extraire vers env-vars.sh
  validate [file]            Valider la structure du fichier
  rotate [file]              Rotation de la clé Age
  help                       Afficher cette aide

Exemples:

  # Créer une nouvelle clé
  $0 create-key

  # Chiffrer le fichier d'exemple
  $0 encrypt secrets/secrets-example.yml secrets/secrets-staging.yml

  # Éditer le fichier de secrets
  $0 edit secrets/secrets-staging.yml

  # Afficher le contenu
  $0 view secrets/secrets-staging.yml

  # Extraire les variables pour développement local
  $0 extract secrets/secrets-staging.yml
  source secrets/env-vars.sh

  # Valider le fichier
  $0 validate secrets/secrets-staging.yml

Variables d'environnement:

  SOPS_AGE_KEY_FILE    Chemin vers la clé Age privée
                       (défaut: ~/.config/sops/age/keys.txt)

Documentation:

  Voir JENKINS_SOPS_GUIDE.md pour plus d'informations

EOF
}

##############################################################################
# Point d'entrée
##############################################################################

main() {
    local command="${1:-help}"
    shift || true
    
    print_header
    
    case "$command" in
        create-key)
            check_dependencies
            cmd_create_key "$@"
            ;;
        encrypt)
            check_dependencies
            cmd_encrypt "$@"
            ;;
        decrypt)
            check_dependencies
            cmd_decrypt "$@"
            ;;
        edit)
            check_dependencies
            cmd_edit "$@"
            ;;
        view)
            check_dependencies
            cmd_view "$@"
            ;;
        extract)
            check_dependencies
            cmd_extract "$@"
            ;;
        validate)
            check_dependencies
            cmd_validate "$@"
            ;;
        rotate)
            check_dependencies
            cmd_rotate "$@"
            ;;
        help|--help|-h)
            cmd_help
            ;;
        *)
            print_error "Commande inconnue: $command"
            echo ""
            cmd_help
            exit 1
            ;;
    esac
}

main "$@"
