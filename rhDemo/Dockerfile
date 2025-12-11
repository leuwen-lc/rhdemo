# ═══════════════════════════════════════════════════════════════════
# Dockerfile pour l'application RHDemo API
# Image de base : Eclipse Temurin 21 (OpenJDK)
# Build multi-stage pour optimiser la taille de l'image finale
# ═══════════════════════════════════════════════════════════════════

# ───────────────────────────────────────────────────────────────────
# STAGE 1 : BUILD
# Construction de l'application avec Maven
# ───────────────────────────────────────────────────────────────────
FROM maven:3.9-eclipse-temurin-21-jammy AS builder

LABEL stage=builder

WORKDIR /build

# Copier les fichiers de configuration Maven
COPY pom.xml .
COPY .mvn .mvn
COPY mvnw .

# Télécharger les dépendances (layer séparé pour le cache)
# Cette étape est mise en cache si pom.xml ne change pas
RUN ./mvnw dependency:go-offline -B

# Copier le code source backend et frontend
COPY src ./src
COPY frontend ./frontend

# Compiler et packager l'application (skip tests pour accélérer le build)
# Les tests sont exécutés séparément dans le pipeline Jenkins
RUN ./mvnw clean package -DskipTests -B

# Vérifier que le JAR a bien été créé
RUN ls -lh /build/target/*.jar

# ───────────────────────────────────────────────────────────────────
# STAGE 2 : RUNTIME
# Image finale légère avec uniquement le JRE et l'application
# ───────────────────────────────────────────────────────────────────
FROM eclipse-temurin:21-jre-jammy

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
    useradd -r -g spring -u 1000 spring && \
    chown -R spring:spring /app

# ───────────────────────────────────────────────────────────────────
# COPIER LE JAR DEPUIS L'ÉTAPE DE BUILD
# ───────────────────────────────────────────────────────────────────
COPY --from=builder --chown=spring:spring /build/target/*.jar app.jar

# ───────────────────────────────────────────────────────────────────
# CONFIGURATION JVM
# ───────────────────────────────────────────────────────────────────
# UseContainerSupport : Détecte les limites de mémoire du container
# MaxRAMPercentage : Utilise max 75% de la RAM disponible pour la heap
# UseG1GC : Garbage Collector G1 (recommandé pour Java 21)
# +ExitOnOutOfMemoryError : Arrêter proprement en cas d'OOM
ENV JAVA_OPTS="-XX:+UseContainerSupport \
               -XX:MaxRAMPercentage=75.0 \
               -XX:+UseG1GC \
               -XX:+ExitOnOutOfMemoryError \
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
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/actuator/health || exit 1

# ───────────────────────────────────────────────────────────────────
# POINT D'ENTRÉE
# ───────────────────────────────────────────────────────────────────
# Utiliser exec form pour une bonne gestion des signaux (SIGTERM, etc.)
ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]
