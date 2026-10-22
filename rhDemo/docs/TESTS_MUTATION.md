---
statut: actif
verifie_le: 2026-10-22
sources:
  - rhDemo/pom.xml
---

# Tests de mutation (PIT)

## Principe

La couverture de code (JaCoCo) mesure les lignes **exécutées** par les tests, pas ce qu'ils **vérifient**.
Le mutation testing comble ce manque : PIT modifie légèrement le code de production (un « mutant »)
puis relance les tests.

| Exemple de mutation | Effet attendu |
|---|---|
| `>` devient `>=` | un test doit échouer |
| `return x` devient `return null` | un test doit échouer |
| suppression d'un appel de méthode | un test doit échouer |

- Si un test échoue, le mutant est **tué** : les tests sont pertinents.
- Si tous les tests passent, le mutant **survit** : un test est trop faible ou manquant.

Le score de mutation est le pourcentage de mutants tués.

## Usage occasionnel, hors CI

PIT est dans un profil Maven `mutation` de [pom.xml](../pom.xml), **non activé par défaut**.
Il n'a aucun impact sur le build, Surefire, Failsafe, JaCoCo, SonarQube ni les pipelines Jenkins.

## Lancer l'analyse

Depuis `rhDemo/` :

```bash
./mvnw -Pmutation test-compile org.pitest:pitest-maven:mutationCoverage
```

- Durée : environ 15 secondes.
- Prérequis : accès à Maven Central la première fois (téléchargement du plugin), et une suite de tests unitaires verte.
  PIT refuse de tourner si un test échoue sans mutation.

## Lire les résultats

- Rapport HTML : `target/pit-reports/index.html`. Il montre, classe par classe, les lignes avec leurs mutants.
- Rapport XML : `target/pit-reports/mutations.xml`, pour un traitement par script.
- Le résumé en fin de console donne `Generated N mutations Killed M (X%)` et la « test strength ».

Statuts d'un mutant :

| Statut | Signification | Action |
|---|---|---|
| `KILLED` | un test a échoué | rien |
| `SURVIVED` | les tests passent malgré la mutation | renforcer ou ajouter un test |
| `NO_COVERAGE` | aucun test unitaire n'exécute la ligne | ajouter un test, ou ignorer si couvert par un `*IT` |
| `TIMED_OUT` | boucle infinie provoquée par la mutation | considéré comme tué |

Un mutant **équivalent** change le code sans changer le comportement observable. Par exemple, retourner
`emptyList()` quand la liste est déjà vide. Il survit légitimement et n'appelle aucun test.

## Périmètre configuré

Défini dans le profil `mutation` de [pom.xml](../pom.xml) :

- **Classes mutées** : `service.*`, `dto.*` et `springconfig.*` sous `fr.leuwen.rhdemoAPI`.
- **Tests utilisés** : tests unitaires `*Test` uniquement. Les `*IT` (`@SpringBootTest`) sont exclus car ils sont trop lents
  pour être relancés pour chaque mutant.
- **Conséquence** : le code couvert seulement par des `*IT` (contrôleurs, `SecurityConfig`, accesseurs de DTO)
  apparaît en `NO_COVERAGE`. C'est un faux positif.

Pour élargir le périmètre, modifier `targetClasses` dans le profil. Un périmètre plus large allonge la durée.

## Premiers résultats (2026-10-21)

- Avant les tests ciblés : 94 mutants, 80 tués (85 %), 14 non tués.
- Après ajout de tests (cookie CSRF `Secure`/`SameSite`, `SpaCsrfTokenRequestHandler`, cas de port 0) :
  tous les mutants de logique visés sont tués.
- Il reste un mutant équivalent (`GrantedAuthoritiesKeyCloakMapper`) et des faux positifs liés au périmètre `*Test`.

## Bonnes pratiques

- Lancer PIT après avoir ajouté de la logique de sécurité ou métier, ou avant une release.
- Traiter en priorité les survivants sur du code de sécurité (CSRF, CSP, rôles, redirections).
- Ne pas viser 100 % : les mutants équivalents et les faux positifs sont normaux.
- Le code de test ajouté doit respecter le quality gate SonarQube (voir [CLAUDE.md](../../CLAUDE.md)).
- Les versions de `pitest-maven` et `pitest-junit5-plugin` sont écrites en dur dans le profil. Penser à les mettre à jour
  de temps en temps.

## Pistes d'évolution

- Job Jenkins dédié, hebdomadaire ou nocturne, publiant le rapport HTML. Le déclencheur `cron` de
  [jenkins-casc.yaml](../infra/jenkins-docker/jenkins-casc.yaml) montre comment le planifier.
- Seuil `mutationThreshold` une fois la base stabilisée.
- Analyse incrémentale avec `withHistory` pour réduire la durée.
- Équivalent frontend : Stryker Mutator, pertinent seulement s'il existe des tests unitaires Vue.
