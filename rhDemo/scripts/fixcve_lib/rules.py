"""Règles métier et constantes de fixcve-auto, en un seul endroit.

Tous les autres modules (et fixcve-detect.py, fixcve-validate-json.py) importent
d'ici : aucun seuil, aucune liste d'images ni aucun nom d'image du projet ne doit être recopié
ailleurs (contrôlé par tests/test_rules.py). Justification des règles : docs/FIXCVE_AUTO.md.
"""
from dataclasses import dataclass

# ----------------------------------------------------------------------------------------------
# Seuils CVSS
# ----------------------------------------------------------------------------------------------

# Seuil d'échec des scans de RHDemo-CI (failBuildOnCVSS de Dependency-Check) : un finding en
# dessous ne fait pas échouer le build, il n'est donc ni détecté ni revérifié.
CVSS_FAIL_THRESHOLD = 7.0
# Au-dessus (inclus), un finding sans correctif ni critère A bloque : le critère B (acceptation
# temporaire) est interdit.
CVSS_BLOCKING = 9.0

# ----------------------------------------------------------------------------------------------
# Images
# ----------------------------------------------------------------------------------------------

# Image de l'application : ses dépendances sont celles du pom.xml et du package.json du projet.
# Tous les findings Dependency-Check lui sont rattachés.
PROJECT_IMAGE = "rhdemo-app"

# Noms des rapports Trivy de Jenkinsfile-CI (stage « Scan Sécurité Images Docker ») : images
# d'ephemere, puis images de global.images du chart rhdemo (values.yaml) non déjà couvertes, le
# suffixe « -stagingkub » signalant une référence qui diverge de celle d'ephemere.
TRIVY_IMAGES = (PROJECT_IMAGE, "nginx", "postgres", "keycloak",
                "busybox", "postgres-exporter", "postgres-stagingkub", "keycloak-stagingkub")

# Images tierces remédiables automatiquement (nouveau tag + digest dans Jenkinsfile-CI) : jeton
# d'image -> dépôt de registre et variable *_IMAGE. Les autres images de TRIVY_IMAGES sont
# détectées mais jamais remédiées automatiquement.
DOCKER_HUB = "registry-1.docker.io"
REMEDIABLE_IMAGES = {
    "keycloak": {"registry": DOCKER_HUB, "path": "keycloak/keycloak",
                 "repository": "keycloak/keycloak", "variable": "KEYCLOAK_IMAGE"},
    "nginx": {"registry": DOCKER_HUB, "path": "library/nginx",
              "repository": "nginx", "variable": "NGINX_IMAGE"},
    "postgres": {"registry": DOCKER_HUB, "path": "library/postgres",
                 "repository": "postgres", "variable": "POSTGRES_IMAGE"},
}

# ----------------------------------------------------------------------------------------------
# Nature du composant (P1 de docs/etudes/FIXCVE_REGLES_METIER.md)
# ----------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Kind:
    name: str
    # Où se fait la montée de version : "pom", "npm", "image" (tag + digest), None (jamais).
    fix_target: str | None
    # Critère A applicables (preuve d'inexposition calculée par script).
    scope_criterion: bool = False      # portées Maven test/provided uniquement
    dev_only_criterion: bool = False   # toutes les copies npm en dev=true
    # Suppression temporaire revérifiable automatiquement (avis OSV + registre du projet).
    reverifiable: bool = False


KINDS = {k.name: k for k in (
    # Dépendance déclarée dans le pom.xml du projet.
    Kind("project_maven", fix_target="pom", scope_criterion=True, reverifiable=True),
    # Dépendance du package.json du frontend.
    Kind("project_npm", fix_target="npm", dev_only_criterion=True, reverifiable=True),
    # Bibliothèque JavaScript embarquée dans un jar (RetireJS, `pkg:javascript/`) : aucun
    # registre à interroger, décision humaine (incident #972).
    Kind("jar_embedded_js", fix_target=None),
    # Paquet système ou binaire d'une image : la version corrigée est celle d'un paquet de la
    # distribution, jamais un tag d'image ; aucune montée automatique.
    Kind("image_os", fix_target=None),
    # Bibliothèque embarquée dans une image tierce (ex. keycloak-services dans keycloak/keycloak) :
    # seul un nouveau tag d'image corrige, jamais une édition du pom.xml (incident #812).
    Kind("image_embedded_jar", fix_target="image"),
)}


def kind_name(ecosystem, image):
    """Nature du composant d'après l'écosystème et l'image du finding."""
    if ecosystem == "javascript":
        return "jar_embedded_js"
    if ecosystem == "docker":
        return "image_os"
    if image != PROJECT_IMAGE:
        return "image_embedded_jar"
    return "project_npm" if ecosystem == "npm" else "project_maven"


def kind_of(item):
    """Nature d'un finding ou d'une action : champ `component_kind`, calculé s'il manque (fichiers
    de cycle antérieurs au champ, findings construits à la main)."""
    return KINDS[item.get("component_kind") or kind_name(item["ecosystem"], item["image"])]


# ----------------------------------------------------------------------------------------------
# Stages de RHDemo-CI traités
# ----------------------------------------------------------------------------------------------

# Ordre d'exécution dans Jenkinsfile-CI : Dependency-Check avant Trivy.
STAGE_ORDER = {"owasp": 1, "trivy": 2}


def stage_type(stage_name):
    """Type de scan d'après le nom d'un stage Jenkins, ou None (hors périmètre)."""
    name = (stage_name or "").lower()
    if "trivy" in name:
        return "trivy"
    if "owasp" in name or "dependency" in name:
        return "owasp"
    return None


# ----------------------------------------------------------------------------------------------
# Règles de cycle du poller (fixcve_lib/cycle.py)
# ----------------------------------------------------------------------------------------------

# Halte après N rollbacks consécutifs (correctifs poussés puis annulés).
MAX_CONSECUTIVE_ROLLBACKS = 2
# Halte après N échecs consécutifs d'une étape avant tout push de correctif (schéma invalide,
# étape sans résultat...) : panne systématique de la procédure.
MAX_CONSECUTIVE_PREPUSH_FAILURES = 2
# Halte après N pushes « no action » consécutifs (stage Trivy/OWASP en échec, aucune CVE
# exploitable) : filet de la boucle des builds #799-#802.
MAX_CONSECUTIVE_NO_ACTION_PUSHES = 2
# Blocage confirmé sur un code source inchangé : silence, puis nouvelle recherche après ce délai
# (un correctif a pu être publié entre-temps).
BLOCKED_RECHECK_SECONDS = 48 * 3600
# Recherche de correctif en panne (OSV, registre) : nouvel essai après ce délai, au plus N fois sur
# le même code source, puis délai normal et alerte. Sans plafond, chaque push de journal
# relancerait un build (boucle).
TRANSIENT_RECHECK_SECONDS = 3600
TRANSIENT_MAX_ATTEMPTS = 3
