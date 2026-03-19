#!/usr/bin/env groovy

/**
 * Bibliothèque de fonctions réutilisables pour le pipeline Jenkins rhDemo
 *
 * Cette bibliothèque contient des fonctions utilitaires pour :
 * - Gestion des secrets
 * - Healthchecks des services
 * - Scan de sécurité Trivy
 * - Gestion des réseaux Docker
 * - Publication de rapports HTML
 */

/**
 * Charge les secrets depuis un fichier bash
 * @param secretsPath Chemin vers le fichier de secrets (défaut: rhDemo/secrets/env-vars.sh)
 */
def loadSecrets(String secretsPath = 'rhDemo/secrets/env-vars.sh') {
    echo "🔐 Chargement des secrets depuis ${secretsPath}"
    sh """
        set +x
        if [ -f "${secretsPath}" ]; then
            . ${secretsPath}
            echo "✅ Secrets chargés"
        else
            echo "⚠️  Fichier de secrets non trouvé: ${secretsPath}"
        fi
        set -x
    """
}

/**
 * Attend qu'un service soit disponible via healthcheck HTTP
 * Test effectué depuis Jenkins (qui doit être connecté au réseau Docker si nécessaire)
 *
 * @param config Map de configuration avec les clés:
 *   - url: URL du healthcheck (requis) - peut être une URL réseau Docker (ex: http://keycloak-ephemere:8080)
 *   - timeout: Timeout en secondes (défaut: 60)
 *   - name: Nom du service pour les logs (défaut: 'Service')
 *   - container: Nom du container pour afficher les logs en cas d'échec (optionnel)
 *   - initialWait: Temps d'attente initial avant de commencer les checks (défaut: 0)
 *   - acceptedCodes: Liste des codes HTTP acceptés (défaut: [200])
 *   - insecure: Ignorer les erreurs SSL pour HTTPS (défaut: false)
 */
def waitForHealthcheck(Map config) {
    def timeout = config.timeout ?: 60
    def name = config.name ?: 'Service'
    def initialWait = config.initialWait ?: 0
    def acceptedCodes = config.acceptedCodes ?: [200]
    def insecure = config.insecure ? '-k' : ''
    def codesPattern = acceptedCodes.join('|')

    if (initialWait > 0) {
        echo "⏳ Attente initiale de ${initialWait}s avant healthcheck ${name}..."
        sleep initialWait
    }

    echo "⏳ Healthcheck ${name} (${timeout}s max)..."

    sh """#!/bin/bash
        timeout=${timeout}
        while [ \$timeout -gt 0 ]; do
            # Test depuis Jenkins (connecté au réseau Docker si nécessaire)
            HTTP_CODE=\$(curl ${insecure} -sf -o /dev/null -w "%{http_code}" "${config.url}" 2>/dev/null || echo "000")

            if echo "\${HTTP_CODE}" | grep -qE "^(${codesPattern})\$"; then
                echo "✅ ${name} ready (HTTP \${HTTP_CODE})"
                exit 0
            fi

            echo "   HTTP \${HTTP_CODE} - retry dans 2s... (reste \${timeout}s)"
            sleep 2
            timeout=\$((timeout - 2))
        done

        echo "❌ ${name} timeout après ${timeout}s"
        ${config.container ? "docker logs --tail=150 ${config.container} 2>&1 || true" : ''}
        exit 1
    """
}

/**
 * Génère un rapport de scan Trivy pour une image Docker
 * @param image Nom complet de l'image Docker
 * @param reportName Nom du rapport (utilisé pour les fichiers de sortie)
 */
def generateTrivyReport(String image, String reportName) {
    sh """#!/bin/bash
        WORKSPACE_DIR=\$(pwd)
        IMAGE="${image}"
        NAME="${reportName}"

        echo "🔍 Scan Trivy: \${IMAGE}"

        # Créer un cache dédié pour ce scan en copiant le cache partagé
        # Évite les conflits d'accès concurrent entre scans parallèles
        # La DB a été téléchargée une seule fois dans .trivy-cache-shared
        TRIVY_CACHE_SHARED="\${WORKSPACE_DIR}/.trivy-cache-shared"
        TRIVY_CACHE_DIR="\${WORKSPACE_DIR}/.trivy-cache-\${NAME}"

        if [ -d "\${TRIVY_CACHE_SHARED}" ]; then
            echo "📦 Copie du cache partagé vers cache dédié \${NAME}..."
            cp -r "\${TRIVY_CACHE_SHARED}" "\${TRIVY_CACHE_DIR}"
            echo "✅ Cache dédié prêt"
        else
            echo "⚠️  Cache partagé non trouvé, création d'un cache vide"
            mkdir -p "\${TRIVY_CACHE_DIR}"
        fi

        export TRIVY_CACHE_DIR

        # Scan JSON pour analyse programmatique
        # --skip-db-update : DB déjà copiée depuis le cache partagé
        # --skip-java-db-update : Évite la mise à jour de la Java DB
        # --no-progress : Désactive la barre de progression (mieux pour logs CI/CD)
        # --ignorefile : Exclut les CVE documentées comme faux positifs (voir SECURITY_ADVISORIES.md)
        TRIVYIGNORE="\${WORKSPACE_DIR}/rhDemo/.trivyignore.yaml"
        IGNOREFILE_OPT=""
        if [ -f "\${TRIVYIGNORE}" ]; then
            IGNOREFILE_OPT="--ignorefile \${TRIVYIGNORE}"
            echo "📋 Utilisation de .trivyignore.yaml (\$(grep -c '- id: CVE-' "\${TRIVYIGNORE}") CVE exclues)"
        fi

        timeout 5m trivy image \\
            --skip-db-update \\
            --skip-java-db-update \\
            --no-progress \\
            --severity CRITICAL,HIGH,MEDIUM \\
            \${IGNOREFILE_OPT} \\
            --format json \\
            --output "\${WORKSPACE_DIR}/trivy-reports/\${NAME}.json" \\
            "\${IMAGE}" 2>&1 | grep -E "(Downloading|Analyzing|Total)" || true

        # Créer un fichier JSON vide si le scan échoue
        if [ ! -f "\${WORKSPACE_DIR}/trivy-reports/\${NAME}.json" ]; then
            echo '{"Results":[]}' > "\${WORKSPACE_DIR}/trivy-reports/\${NAME}.json"
        fi

        # Scan format table pour lecture humaine
        timeout 3m trivy image \\
            --skip-db-update \\
            --skip-java-db-update \\
            --no-progress \\
            --severity CRITICAL,HIGH,MEDIUM \\
            \${IGNOREFILE_OPT} \\
            --format table \\
            --output "\${WORKSPACE_DIR}/trivy-reports/\${NAME}.txt" \\
            "\${IMAGE}" 2>&1 || echo "⚠️  Scan table timeout ou erreur pour \${NAME}"

        # Nettoyer le cache dédié après le scan pour économiser l'espace disque
        rm -rf "\${TRIVY_CACHE_DIR}"

        # Générer le rapport HTML stylisé
        if [ -f "\${WORKSPACE_DIR}/trivy-reports/\${NAME}.txt" ]; then
            echo "📄 Génération rapport HTML pour \${NAME}..."
            {
                echo '<!DOCTYPE html><html><head><meta charset="UTF-8">'
                echo "<title>Trivy Report - \${IMAGE}</title>"
                echo '<style>body{font-family:monospace;margin:20px;background:#f5f5f5} pre{background:white;padding:20px;border-radius:5px;overflow-x:auto;box-shadow:0 2px 4px rgba(0,0,0,0.1)} h1{color:#333}.critical{color:#d32f2f;font-weight:bold}.high{color:#f57c00}.medium{color:#fbc02d}</style></head>'
                echo "<body><h1>🔒 Trivy Security Report</h1><h2>Image: \${IMAGE}</h2><pre>"
                cat "\${WORKSPACE_DIR}/trivy-reports/\${NAME}.txt" | sed 's|CRITICAL|<span class="critical">CRITICAL</span>|g; s|HIGH|<span class="high">HIGH</span>|g; s|MEDIUM|<span class="medium">MEDIUM</span>|g'
                echo '</pre></body></html>'
            } > "\${WORKSPACE_DIR}/trivy-reports/\${NAME}.html"
            echo "✅ Rapport HTML \${NAME}.html créé"
        else
            echo "⚠️  Fichier \${NAME}.txt introuvable - HTML non généré"
            # Créer un HTML vide pour indiquer qu'il n'y a pas de rapport
            {
                echo '<!DOCTYPE html><html><head><meta charset="UTF-8">'
                echo "<title>Trivy Report - \${IMAGE}</title>"
                echo '<style>body{font-family:monospace;margin:20px;background:#f5f5f5}</style></head>'
                echo "<body><h1>⚠️  Rapport Trivy non disponible</h1>"
                echo "<p>Le scan format table n'a pas pu être généré pour \${IMAGE}.</p>"
                echo "<p>Consultez le rapport JSON pour plus de détails.</p>"
                echo "</body></html>"
            } > "\${WORKSPACE_DIR}/trivy-reports/\${NAME}.html"
        fi

        echo "✅ Scan ${reportName} terminé"
    """
}

/**
 * Agrège les résultats de tous les scans Trivy et vérifie les seuils
 * @return true si aucune vulnérabilité CRITICAL, false sinon
 */
def aggregateTrivyResults() {
    echo "📊 Agrégation des résultats Trivy..."

    def result = sh(
        script: '''#!/bin/bash
            echo ""
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "📊 RÉSULTATS GLOBAUX TRIVY"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

            TOTAL_CRITICAL=0
            TOTAL_HIGH=0
            TOTAL_MEDIUM=0
            FAILED=false

            for REPORT in trivy-reports/*.json; do
                [ -f "$REPORT" ] || continue
                CRITICAL=$(jq '[.Results[]?.Vulnerabilities[]? | select(.Severity=="CRITICAL")] | length' "$REPORT" 2>/dev/null || echo "0")
                HIGH=$(jq '[.Results[]?.Vulnerabilities[]? | select(.Severity=="HIGH")] | length' "$REPORT" 2>/dev/null || echo "0")
                MEDIUM=$(jq '[.Results[]?.Vulnerabilities[]? | select(.Severity=="MEDIUM")] | length' "$REPORT" 2>/dev/null || echo "0")

                TOTAL_CRITICAL=$((TOTAL_CRITICAL + CRITICAL))
                TOTAL_HIGH=$((TOTAL_HIGH + HIGH))
                TOTAL_MEDIUM=$((TOTAL_MEDIUM + MEDIUM))

                if [ "$CRITICAL" -gt 0 ]; then
                    FAILED=true
                fi
            done

            printf "   Total CRITICAL : %3d\\n" "$TOTAL_CRITICAL"
            printf "   Total HIGH     : %3d\\n" "$TOTAL_HIGH"
            printf "   Total MEDIUM   : %3d\\n" "$TOTAL_MEDIUM"
            echo ""

            if [ "$FAILED" = true ]; then
                echo "❌ ÉCHEC: $TOTAL_CRITICAL vulnérabilités CRITICAL détectées"
                echo "   Les rapports détaillés sont disponibles dans trivy-reports/"
                exit 1
            else
                echo "✅ SUCCÈS: Aucune vulnérabilité CRITICAL détectée"
                if [ "$TOTAL_HIGH" -gt 0 ]; then
                    echo "   ⚠️  Attention: $TOTAL_HIGH vulnérabilités HIGH détectées (non bloquantes)"
                fi
                exit 0
            fi
        ''',
        returnStatus: true
    )

    return result == 0
}

/**
 * Crée un réseau Docker s'il n'existe pas déjà
 * @param network Nom du réseau
 */
def dockerNetworkCreate(String network) {
    echo "🌐 Création du réseau Docker ${network}..."
    sh """
        docker network create ${network} 2>/dev/null || echo "✓ Réseau ${network} existe déjà"
    """
}

/**
 * Connecte un container à un réseau Docker
 * @param container Nom du container
 * @param network Nom du réseau
 */
def dockerNetworkConnect(String container, String network) {
    echo "🔗 Connexion de ${container} au réseau ${network}..."
    sh """
        docker network connect ${network} ${container} 2>/dev/null || echo "⚠️  ${container} déjà connecté à ${network}"
    """
}

/**
 * Déconnecte un container d'un réseau Docker
 * @param container Nom du container
 * @param network Nom du réseau
 */
def dockerNetworkDisconnect(String container, String network) {
    echo "🔌 Déconnexion de ${container} du réseau ${network}..."
    sh """
        docker network disconnect ${network} ${container} 2>/dev/null || echo "⚠️  ${container} déjà déconnecté de ${network}"
    """
}

/**
 * Nettoie de manière sécurisée les fichiers contenant des secrets
 * @param files Liste des chemins de fichiers à supprimer
 */
def cleanupSecrets(List files) {
    echo "🧹 Nettoyage sécurisé des fichiers de secrets..."

    files.each { file ->
        sh """
            if [ -f "${file}" ]; then
                # -u : unlink (supprime le fichier après écrasement) - OBLIGATOIRE pour réellement effacer
                # -z : passe finale à zéro (masque l'écrasement)
                # -n 3 : 3 passes d'écrasement
                shred -vfzu -n 3 ${file} 2>/dev/null || rm -f ${file}
                echo "✅ ${file} supprimé de manière sécurisée"
            fi
        """
    }
}

/**
 * Publie un rapport HTML dans Jenkins
 * @param reportDir Répertoire contenant le rapport
 * @param reportFile Nom du fichier HTML
 * @param reportName Nom affiché dans Jenkins
 */
def publishHTMLReport(String reportDir, String reportFile, String reportName) {
    publishHTML([
        reportDir: reportDir,
        reportFiles: reportFile,
        reportName: reportName,
        allowMissing: true,
        keepAll: true,
        alwaysLinkToLastBuild: true
    ])
}

/**
 * Publie plusieurs rapports HTML d'un coup
 * @param reports Liste de Maps [reportDir, reportFile, reportName]
 */
def publishHTMLReports(List reports) {
    echo "📊 Publication de ${reports.size()} rapports HTML..."

    reports.each { report ->
        publishHTMLReport(report[0], report[1], report[2])
    }
}

/**
 * Trouve le container Jenkins principal (exclut les agents)
 * @return Nom du container Jenkins ou null si non trouvé
 */
def findJenkinsContainer() {
    def container = sh(
        script: 'docker ps --filter "name=jenkins" --format "{{.Names}}" | grep -v agent | head -n 1',
        returnStdout: true
    ).trim()

    if (container) {
        echo "✅ Container Jenkins trouvé: ${container}"
        return container
    } else {
        echo "⚠️  Container Jenkins non trouvé"
        return null
    }
}

/**
 * Affiche un séparateur visuel dans les logs
 * @param title Titre de la section
 */
def printSectionHeader(String title) {
    echo '═══════════════════════════════════════════════════════'
    echo "  ${title}"
    echo '═══════════════════════════════════════════════════════'
}

/**
 * Exécute une commande avec les secrets chargés
 * @param secretsPath Chemin vers le fichier de secrets
 * @param command Commande à exécuter
 */
def withSecretsLoaded(String secretsPath, String command) {
    sh """
        set +x
        . ${secretsPath}
        set -x
        ${command}
    """
}

// Retourner this pour permettre l'import
return this
