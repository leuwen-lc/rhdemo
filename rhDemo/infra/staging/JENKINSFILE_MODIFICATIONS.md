# Jenkinsfile - Modifications pour Tests Selenium avec Docker Compose

## SECTIONS À AJOUTER APRÈS PHASE 3

### 📝 1. Nouvelles variables d'environnement (section environment)

```groovy
environment {
    // ... variables existantes ...
    
    // Environnement de test isolé (NOUVEAU)
    STAGING_INFRA_PATH = 'rhDemo/infra/staging'
    KEYCLOAK_INIT_PATH = '../rhDemoInitKeycloak'
    TEST_DOMAIN = 'rhdemo.staging.local'
    KEYCLOAK_DOMAIN = 'keycloak.staging.local'
    
    // Image avec build number pour tracking (NOUVEAU)
    IMAGE_TAG_BUILD = "${APP_VERSION}-${BUILD_NUMBER}"
}
```

---

### 🐳 2. PHASE 4 : ENVIRONNEMENT DE TEST ISOLÉ (NOUVEAU - Insérer après Phase 3)

```groovy
// ════════════════════════════════════════════════════════════════
// PHASE 4 : ENVIRONNEMENT DE TEST ISOLÉ
// ════════════════════════════════════════════════════════════════

stage('📝 Configuration Environnement Test') {
    steps {
        script {
            echo '═══════════════════════════════════════════════════════'
            echo '  PHASE 4 : ENVIRONNEMENT DE TEST ISOLÉ'
            echo '═══════════════════════════════════════════════════════'
            echo '▶ Génération du fichier .env pour Docker Compose...'
        }
        sh '''
            . rhDemo/secrets/env-vars.sh
            
            cd ${STAGING_INFRA_PATH}
            
            # Générer le fichier .env
            cat > .env <<EOF
# Généré automatiquement par Jenkins Build #${BUILD_NUMBER}
# $(date)

# Base de données PostgreSQL
RHDEMO_DB_PASSWORD=${RHDEMO_DATASOURCE_PASSWORD_PG}
KEYCLOAK_DB_PASSWORD=keycloak_db_jenkins_${BUILD_NUMBER}
KEYCLOAK_ADMIN_PASSWORD=admin_jenkins_${BUILD_NUMBER}

# Keycloak OAuth2
RHDEMO_KEYCLOAK_CLIENT_SECRET=${RHDEMO_CLIENT_REGISTRATION_KEYCLOAK_CLIENT_SECRET}

# Image Docker (buildée par Maven)
RHDEMO_IMAGE=${DOCKER_IMAGE_NAME}:${IMAGE_TAG_BUILD}

# Domaines
RHDEMO_DOMAIN=${TEST_DOMAIN}
KEYCLOAK_DOMAIN=${KEYCLOAK_DOMAIN}
EOF
            
            echo "✅ Fichier .env créé"
            echo "Image utilisée: ${DOCKER_IMAGE_NAME}:${IMAGE_TAG_BUILD}"
        '''
    }
}

stage('🔐 Génération Certificats SSL') {
    steps {
        script {
            echo '▶ Génération des certificats SSL auto-signés...'
        }
        sh '''
            cd ${STAGING_INFRA_PATH}
            
            # Exécuter le script de génération
            ./generate-certs.sh \
                --rhdemo-domain ${TEST_DOMAIN} \
                --keycloak-domain ${KEYCLOAK_DOMAIN}
            
            # Vérifier que les certificats sont créés
            if [ ! -f certs/nginx.crt ] || [ ! -f certs/nginx.key ]; then
                echo "❌ Erreur: Certificats non générés"
                exit 1
            fi
            
            echo "✅ Certificats SSL générés"
            ls -lh certs/
        '''
    }
}

stage('🏷️ Tag Image Docker') {
    steps {
        script {
            echo '▶ Tag de l\'image Docker avec le numéro de build...'
        }
        sh '''
            # Vérifier que l'image SNAPSHOT existe
            if ! docker images | grep "${DOCKER_IMAGE_NAME}.*${APP_VERSION}"; then
                echo "❌ Image ${DOCKER_IMAGE_NAME}:${APP_VERSION} introuvable"
                exit 1
            fi
            
            # Tagger avec le numéro de build
            docker tag ${DOCKER_IMAGE_NAME}:${APP_VERSION} \
                       ${DOCKER_IMAGE_NAME}:${IMAGE_TAG_BUILD}
            
            echo "✅ Image taguée: ${DOCKER_IMAGE_NAME}:${IMAGE_TAG_BUILD}"
            docker images | grep ${DOCKER_IMAGE_NAME}
        '''
    }
}

stage('🚀 Démarrage Environnement Docker') {
    steps {
        script {
            echo '▶ Démarrage de l\'environnement Docker Compose...'
        }
        sh '''
            cd ${STAGING_INFRA_PATH}
            
            # Nettoyer l'environnement précédent si existe
            docker compose -f docker-compose.yml -f docker-compose.jenkins.yml down -v 2>/dev/null || true
            
            # Démarrer tous les services
            docker compose -f docker-compose.yml \
                          -f docker-compose.jenkins.yml \
                          up -d
            
            echo "✅ Services démarrés"
            docker compose ps
        '''
    }
}

stage('⏳ Vérification Healthchecks') {
    steps {
        script {
            echo '▶ Attente de la disponibilité des services...'
        }
        sh '''
            cd ${STAGING_INFRA_PATH}
            
            echo "Vérification PostgreSQL RHDemo..."
            MAX_RETRIES=30
            RETRY=0
            until docker exec rhdemo-staging-db pg_isready -U rhdemo 2>/dev/null; do
                RETRY=$((RETRY + 1))
                if [ $RETRY -ge $MAX_RETRIES ]; then
                    echo "❌ PostgreSQL RHDemo timeout"
                    exit 1
                fi
                echo "  Tentative $RETRY/$MAX_RETRIES..."
                sleep 2
            done
            echo "✅ PostgreSQL RHDemo prêt"
            
            echo "Vérification PostgreSQL Keycloak..."
            RETRY=0
            until docker exec keycloak-staging-db pg_isready -U keycloak 2>/dev/null; do
                RETRY=$((RETRY + 1))
                if [ $RETRY -ge $MAX_RETRIES ]; then
                    echo "❌ PostgreSQL Keycloak timeout"
                    exit 1
                fi
                echo "  Tentative $RETRY/$MAX_RETRIES..."
                sleep 2
            done
            echo "✅ PostgreSQL Keycloak prêt"
            
            echo "Vérification Keycloak..."
            RETRY=0
            until curl -k -s https://${KEYCLOAK_DOMAIN}/health/ready | grep -q "UP\\|status.*up"; do
                RETRY=$((RETRY + 1))
                if [ $RETRY -ge $MAX_RETRIES ]; then
                    echo "❌ Keycloak timeout"
                    docker compose logs keycloak | tail -50
                    exit 1
                fi
                echo "  Tentative $RETRY/$MAX_RETRIES..."
                sleep 3
            done
            echo "✅ Keycloak prêt"
            
            echo "Vérification Application RHDemo..."
            RETRY=0
            until curl -s http://localhost:9000/actuator/health | grep -q "UP\\|status.*UP"; do
                RETRY=$((RETRY + 1))
                if [ $RETRY -ge $MAX_RETRIES ]; then
                    echo "❌ Application RHDemo timeout"
                    docker compose logs rhdemo-app | tail -50
                    exit 1
                fi
                echo "  Tentative $RETRY/$MAX_RETRIES..."
                sleep 3
            done
            echo "✅ Application RHDemo prête"
            
            echo "Vérification Nginx..."
            RETRY=0
            until curl -k -s -o /dev/null -w "%{http_code}" https://${TEST_DOMAIN} | grep -q "200\\|301\\|302"; do
                RETRY=$((RETRY + 1))
                if [ $RETRY -ge $MAX_RETRIES ]; then
                    echo "❌ Nginx timeout"
                    docker compose logs nginx | tail -50
                    exit 1
                fi
                echo "  Tentative $RETRY/$MAX_RETRIES..."
                sleep 2
            done
            echo "✅ Nginx prêt"
            
            echo ""
            echo "╔═══════════════════════════════════════════════════╗"
            echo "║  ✅ Tous les services sont opérationnels !       ║"
            echo "╚═══════════════════════════════════════════════════╝"
        '''
    }
}

stage('🔐 Initialisation Keycloak') {
    steps {
        script {
            echo '▶ Initialisation de Keycloak (realm, client, utilisateurs)...'
        }
        sh '''
            cd ${STAGING_INFRA_PATH}
            
            # Vérifier que rhDemoInitKeycloak est buildé
            if [ ! -f ${KEYCLOAK_INIT_PATH}/target/rhDemoInitKeycloak-1.0.0.jar ]; then
                echo "Build de rhDemoInitKeycloak..."
                cd ${KEYCLOAK_INIT_PATH}
                ./mvnw clean package -DskipTests
                cd -
            fi
            
            # Exécuter le script d'initialisation en mode non-interactif
            ./init-keycloak.sh --non-interactive
            
            # Vérifier que l'initialisation a réussi
            if [ $? -eq 0 ]; then
                echo "✅ Keycloak initialisé avec succès"
            else
                echo "❌ Erreur lors de l'initialisation de Keycloak"
                exit 1
            fi
        '''
    }
}

stage('💾 Initialisation Base de Données') {
    steps {
        script {
            echo '▶ Initialisation de la base de données (schéma + données)...'
        }
        sh '''
            cd ${STAGING_INFRA_PATH}
            
            # Exécuter le script d'initialisation en mode force (pas de confirmation)
            ./init-database.sh --force
            
            # Vérifier le nombre d'employés insérés
            EMPLOYEE_COUNT=$(docker exec rhdemo-staging-db \
                psql -U rhdemo -d rhdemo -t -c "SELECT COUNT(*) FROM employes;" | xargs)
            
            echo "Employés insérés: ${EMPLOYEE_COUNT}"
            
            if [ "$EMPLOYEE_COUNT" -lt 300 ]; then
                echo "❌ Erreur: Nombre d'employés insuffisant (attendu: 303, reçu: ${EMPLOYEE_COUNT})"
                exit 1
            fi
            
            echo "✅ Base de données initialisée avec ${EMPLOYEE_COUNT} employés"
        '''
    }
}

stage('⏱️ Stabilisation Environnement') {
    steps {
        script {
            echo '▶ Attente de stabilisation de l\'environnement...'
        }
        sh '''
            echo "Pause de 30 secondes pour stabilisation complète..."
            sleep 30
            
            # Vérifications finales
            cd ${STAGING_INFRA_PATH}
            docker compose ps
            
            echo ""
            echo "Vérification finale des endpoints..."
            curl -k -s https://${TEST_DOMAIN} > /dev/null && echo "  ✓ RHDemo accessible"
            curl -k -s https://${KEYCLOAK_DOMAIN} > /dev/null && echo "  ✓ Keycloak accessible"
            
            echo ""
            echo "╔═══════════════════════════════════════════════════╗"
            echo "║  ✅ Environnement de test prêt pour Selenium !   ║"
            echo "╚═══════════════════════════════════════════════════╝"
        '''
    }
}
```

---

### 🌐 3. PHASE 5 : TESTS SELENIUM (REMPLACER la section existante)

```groovy
// ════════════════════════════════════════════════════════════════
// PHASE 5 : TESTS SELENIUM SUR ENVIRONNEMENT COMPLET
// ════════════════════════════════════════════════════════════════

stage('🌐 Tests Selenium IHM') {
    when {
        expression { params.RUN_SELENIUM_TESTS == true }
    }
    steps {
        script {
            echo '═══════════════════════════════════════════════════════'
            echo '  PHASE 5 : TESTS SELENIUM SUR ENVIRONNEMENT COMPLET'
            echo '═══════════════════════════════════════════════════════'
            echo '▶ Configuration des tests Selenium...'
        }
        
        dir(TEST_PROJECT_PATH) {
            sh '''
                echo "Configuration des tests Selenium:"
                echo "  URL de base: https://${TEST_DOMAIN}"
                echo "  Keycloak: https://${KEYCLOAK_DOMAIN}"
                echo "  Mode: headless"
                echo ""
                
                # Exécution des tests Selenium
                ../rhDemo/./mvnw clean test \
                    -Dselenium.headless=true \
                    -Dtest.baseurl=https://${TEST_DOMAIN} \
                    -Dkeycloak.url=https://${KEYCLOAK_DOMAIN} \
                    -Dtest.username=manager \
                    -Dtest.password=manager123
                
                echo "✅ Tests Selenium terminés"
            '''
        }
    }
    post {
        always {
            script {
                echo '▶ Archivage des rapports de tests...'
                
                dir(TEST_PROJECT_PATH) {
                    // Screenshots en cas d'échec
                    archiveArtifacts artifacts: '**/screenshots/**/*.png', allowEmptyArchive: true
                    
                    // Rapports JUnit
                    junit testResults: '**/target/surefire-reports/*.xml', allowEmptyResults: true
                    
                    // Logs Selenium (si disponibles)
                    archiveArtifacts artifacts: '**/target/selenium-logs/*.log', allowEmptyArchive: true
                }
            }
        }
        failure {
            script {
                echo '❌ Tests Selenium échoués - Capture des logs Docker...'
                
                sh '''
                    cd ${STAGING_INFRA_PATH}
                    
                    echo "=== LOGS RHDEMO APP ==="
                    docker compose logs --tail=100 rhdemo-app || true
                    
                    echo ""
                    echo "=== LOGS KEYCLOAK ==="
                    docker compose logs --tail=50 keycloak || true
                    
                    echo ""
                    echo "=== LOGS NGINX ==="
                    docker compose logs --tail=30 nginx || true
                '''
            }
        }
    }
}
```

---

### 🧹 4. PHASE 6 : NETTOYAGE (NOUVEAU - Ajouter à la fin du post block)

```groovy
stage('🧹 Nettoyage Environnement Test') {
    steps {
        script {
            echo '═══════════════════════════════════════════════════════'
            echo '  PHASE 6 : NETTOYAGE ENVIRONNEMENT TEST'
            echo '═══════════════════════════════════════════════════════'
            echo '▶ Arrêt et nettoyage de l\'environnement Docker...'
        }
        sh '''
            cd ${STAGING_INFRA_PATH}
            
            # Arrêter et supprimer tous les containers + volumes
            docker compose -f docker-compose.yml \
                          -f docker-compose.jenkins.yml \
                          down -v
            
            # Supprimer les fichiers temporaires
            rm -f .env
            
            # Nettoyer les réseaux orphelins
            docker network prune -f
            
            # Optionnel: Supprimer l'image de build (garder pour cache)
            # docker rmi ${DOCKER_IMAGE_NAME}:${IMAGE_TAG_BUILD} || true
            
            echo "✅ Environnement nettoyé"
        '''
    }
}
```

---

### ⚠️ 5. POST-ACTIONS - Ajouter au bloc `post`

```groovy
post {
    // ... existing always block ...
    
    failure {
        script {
            echo '❌ Pipeline échoué - Capture des logs complets...'
            
            // Logs Docker si l'environnement est encore actif
            sh '''
                cd ${STAGING_INFRA_PATH} 2>/dev/null || exit 0
                
                if docker compose ps 2>/dev/null | grep -q running; then
                    echo "=== ÉTAT DES CONTAINERS ==="
                    docker compose ps
                    
                    echo ""
                    echo "=== LOGS COMPLETS ==="
                    docker compose logs --tail=200
                    
                    # Cleanup forcé
                    docker compose down -v 2>/dev/null || true
                fi
            '''
        }
        
        // ... existing email notification ...
    }
    
    cleanup {
        script {
            echo '▶ Nettoyage final du workspace Jenkins...'
            
            sh '''
                # Supprimer les secrets déchiffrés
                rm -f rhDemo/secrets/env-vars.sh
                rm -f rhDemo/secrets/secrets-decrypted.yml
                
                # Supprimer les certificats temporaires
                rm -rf ${STAGING_INFRA_PATH}/certs/*.crt
                rm -rf ${STAGING_INFRA_PATH}/certs/*.key
                
                echo "✅ Cleanup terminé"
            '''
        }
    }
}
```

---

## 📋 RÉSUMÉ DES MODIFICATIONS

### Fichiers modifiés:
1. ✅ `infra/staging/init-keycloak.sh` - Mode non-interactif
2. ✅ `infra/staging/init-database.sh` - Mode force
3. ✅ `infra/staging/docker-compose.jenkins.yml` - Override image
4. ✅ `infra/staging/generate-certs.sh` - Génération certificats
5. ⏳ `Jenkinsfile` - 6 nouvelles étapes

### Nouvelles étapes Jenkins:
- Configuration Environnement Test (génération .env)
- Génération Certificats SSL
- Tag Image Docker
- Démarrage Environnement Docker (5 services)
- Vérification Healthchecks (PostgreSQL × 2, Keycloak, App, Nginx)
- Initialisation Keycloak (realm + client + users)
- Initialisation Base de Données (303 employés)
- Stabilisation (30s)
- Tests Selenium (sur environnement complet)
- Nettoyage

### Durée estimée du pipeline:
- Build + Tests unitaires: 3-5 min
- Setup environnement: 2-3 min
- Healthchecks + Init: 2-3 min
- Tests Selenium: 3-5 min
- **TOTAL: ~10-16 minutes**

