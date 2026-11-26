# ═══════════════════════════════════════════════════════════════════
# Dockerfile pour l'application RHDemo API
# Image de base : Eclipse Temurin 25 LTS (OpenJDK)
# Build multi-stage pour optimiser la taille de l'image finale
# ═══════════════════════════════════════════════════════════════════

# ───────────────────────────────────────────────────────────────────
# STAGE 1 : BUILD
# Construction de l'application avec Maven et Java 25
# ───────────────────────────────────────────────────────────────────
FROM maven:3.10.0-eclipse-temurin-25-noble@sha256:e3760e0213ee8274e8b7926e5ecfcbabcbef93414c5561c4ecb657e435865329 AS builder

LABEL stage=builder

WORKDIR /build

# Copier les fichiers de configuration Maven
COPY pom.xml .
COPY .mvn .mvn
COPY mvnw .

# Télécharger les dépendances (layer séparé pour le cache)
# Cette étape est mise en cache si pom.xml ne change pas
# -q : n'affiche que les erreurs (sinon liste de tous les plugins et dépendances résolus)
RUN ./mvnw dependency:go-offline -B -q

# Copier le code source backend et frontend
COPY src ./src
COPY frontend ./frontend

# npm : ni annonce de nouvelle version ni lignes « notice » (le plugin Maven les affiche en
# [ERROR] car npm les écrit sur stderr) ; avertissements et erreurs restent affichés
ENV NPM_CONFIG_UPDATE_NOTIFIER=false \
    NPM_CONFIG_LOGLEVEL=warn

# Compiler et packager l'application (skip tests pour accélérer le build)
# Les tests sont exécutés séparément dans le pipeline Jenkins
# -ntp : pas de lignes Downloading/Downloaded pour les artefacts absents du cache
RUN ./mvnw clean package -DskipTests -B -ntp

# Vérifier que le JAR a bien été créé
RUN ls -lh /build/target/*.jar

# ───────────────────────────────────────────────────────────────────
# STAGE 2 : RUNTIME
# Image finale légère avec uniquement le JRE 25 et l'application
# ───────────────────────────────────────────────────────────────────
FROM eclipse-temurin:25.0.5_8-jre-noble@sha256:23481dc33a759b79d62814ceb1ec27a0d1a84da9d7aab0609577427176fbb1b7

# Arguments de build (optionnels, fournis par Jenkins)
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION=1.0.0

LABEL maintainer="RHDemo Team"
LABEL description="RHDemo API - Spring Boot Application"
LABEL version="${VERSION}"
LABEL org.opencontainers.image.created="${BUILD_DATE}"
LABEL org.opencontainers.image.revision="${VCS_REF}"
LABEL org.opencontainers.image.version="${VERSION}"

WORKDIR /app

# ───────────────────────────────────────────────────────────────────
# SÉCURITÉ : Créer un utilisateur non-root
# ───────────────────────────────────────────────────────────────────
RUN groupadd -r spring && \
    useradd -r -g spring spring && \
    chown -R spring:spring /app

# ───────────────────────────────────────────────────────────────────
# COPIER LE JAR DEPUIS L'ÉTAPE DE BUILD
# ───────────────────────────────────────────────────────────────────
COPY --from=builder --chown=spring:spring /build/target/*.jar app.jar

# ───────────────────────────────────────────────────────────────────
# CONFIGURATION JVM (Java 25)
# ───────────────────────────────────────────────────────────────────
# UseContainerSupport : Détecte les limites de mémoire du container
# MaxRAMPercentage : Utilise max 75% de la RAM disponible pour la heap
# UseG1GC : Garbage Collector G1 (default, production-ready)
# Alternative : UseZGC pour faible latence (production-ready en Java 25)
# +ExitOnOutOfMemoryError : Arrêter proprement en cas d'OOM
# -UseBASE64Intrinsics : contournement CVE-2026-114938 (Java4Shell, intrinsèque Base64 AVX-512
#   de C2), Temurin 25.0.5 non corrigé ; à retirer avec un JDK corrigé
ENV JAVA_OPTS="-XX:+UseContainerSupport \
               -XX:MaxRAMPercentage=75.0 \
               -XX:+UseG1GC \
               -XX:+ExitOnOutOfMemoryError \
               -XX:-UseBASE64Intrinsics \
               -Djava.security.egd=file:/dev/./urandom"

# ───────────────────────────────────────────────────────────────────
# PROFILS SPRING BOOT
# ───────────────────────────────────────────────────────────────────
# Profil par défaut (peut être surchargé via variables d'environnement)
ENV SPRING_PROFILES_ACTIVE=production

# ───────────────────────────────────────────────────────────────────
# EXPOSER LE PORT
# ───────────────────────────────────────────────────────────────────
EXPOSE 8080

# ───────────────────────────────────────────────────────────────────
# BASCULER SUR L'UTILISATEUR NON-ROOT
# ───────────────────────────────────────────────────────────────────
USER spring:spring

# ───────────────────────────────────────────────────────────────────
# HEALTHCHECK
# ───────────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=3s --start-period=60s --retries=3 \
    CMD bash -c 'echo > /dev/tcp/localhost/8080' || exit 1

# ───────────────────────────────────────────────────────────────────
# POINT D'ENTRÉE
# ───────────────────────────────────────────────────────────────────
# Utiliser exec form pour une bonne gestion des signaux (SIGTERM, etc.)
ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]
