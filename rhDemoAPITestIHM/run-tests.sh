#!/bin/bash

# Script pour lancer les tests Selenium du projet rhDemoAPITestIHM

echo "🧪 Lancement des tests Selenium pour RH Demo"
echo "=============================================="
echo ""

# Vérifier que l'application est accessible
echo "📡 Vérification que l'application RH Demo est accessible..."
if curl -s http://localhost:9000 > /dev/null 2>&1; then
    echo "✅ Application accessible sur http://localhost:9000"
else
    echo "❌ L'application n'est pas accessible sur http://localhost:9000"
    echo "💡 Démarrez d'abord l'application RH Demo :"
    echo "   cd ../rhdemo && ./mvnw spring-boot:run"
    exit 1
fi

echo ""
echo "🚀 Lancement des tests..."
echo ""

# Lancer les tests Maven
mvn clean test

# Capturer le code de sortie
EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Tous les tests sont passés avec succès!"
else
    echo "❌ Certains tests ont échoué (code: $EXIT_CODE)"
fi

exit $EXIT_CODE
