# Test de la clé API NVD

## Vérifier que la clé est valide

### Méthode 1 : Test avec curl

```bash
# Remplacer YOUR_API_KEY par votre clé
curl -H "apiKey: YOUR_API_KEY" \
  "https://services.nvd.nist.gov/rest/json/cves/2.0?resultsPerPage=1"
```

**Réponse attendue si la clé est valide** :
```json
{
  "resultsPerPage": 1,
  "startIndex": 0,
  "totalResults": ...,
  "format": "NVD_CVE",
  "version": "2.0",
  "vulnerabilities": [...]
}
```

**Réponse si la clé est invalide** :
```json
{
  "message": "Invalid API Key"
}
```

### Méthode 2 : Test avec Maven en local

```bash
cd rhDemo

# Test avec votre clé
./mvnw org.owasp:dependency-check-maven:check -DnvdApiKey=YOUR_API_KEY
```

**Si la clé est valide** : Pas de warning
**Si la clé est invalide** : `[WARNING] The API key has been set but appears to be invalid`

### Méthode 3 : Vérifier l'activation de la clé

Après avoir demandé une clé sur https://nvd.nist.gov/developers/request-an-api-key :

1. **Vous recevez un email** avec la clé
2. **Délai d'activation** : La clé peut prendre quelques heures à 24h pour être activée
3. **Vérifiez l'email** : Assurez-vous d'avoir cliqué sur le lien de confirmation

## Solutions si la clé est invalide

### Solution 1 : Demander une nouvelle clé

1. Aller sur https://nvd.nist.gov/developers/request-an-api-key
2. Remplir le formulaire avec votre email professionnel
3. Confirmer par email
4. Attendre 2-24 heures pour l'activation
5. Mettre à jour le credential Jenkins

### Solution 2 : Continuer sans clé API

Si vous ne pouvez pas obtenir de clé valide, OWASP Dependency-Check fonctionne **sans clé** mais :

- ⚠️ **Plus lent** (limite de 10 requêtes / 30 secondes au lieu de 50)
- ⚠️ **Risque de timeout** au premier scan (téléchargement complet NVD)
- ✅ **Fonctionne** avec les données en cache local

Le pipeline **continuera à fonctionner** même avec ce warning, mais utilisera le cache local NVD uniquement.

### Solution 3 : Vérifier qu'il n'y a pas d'espaces/caractères invisibles

Parfois le credential Jenkins peut contenir des espaces ou caractères invisibles. Pour le vérifier :

1. **Copier la clé depuis l'email** dans un éditeur de texte
2. **Supprimer tous les espaces** avant/après
3. **Copier à nouveau** la clé propre
4. **Mettre à jour le credential Jenkins**
5. **Relancer un build**

## Format de la clé valide

```
xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

Où chaque `x` est un caractère hexadécimal (0-9, a-f).

**Exemple** : `f9e4e2c2-1a2b-3c4d-5e6f-7890abcdef12`

## Vérifier dans les logs Jenkins

Dans les logs du build, cherchez :

**Avec clé valide** :
```
✅ Clé API NVD configurée
[INFO] Downloading NVD data...
```

**Avec clé invalide** :
```
✅ Clé API NVD configurée
[WARNING] The API key has been set but appears to be invalid
```

**Sans clé** :
```
⚠️  Clé API NVD non configurée - l'analyse sera plus lente
```

## Impact du warning

Même avec ce warning, le pipeline :
- ✅ Continue l'analyse
- ✅ Utilise le cache local NVD
- ✅ Détecte les vulnérabilités
- ⚠️ Mais les données peuvent être obsolètes

**Recommandation** : Résolvez ce warning pour avoir les dernières vulnérabilités à jour.
