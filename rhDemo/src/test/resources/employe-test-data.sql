-- Données de test pour les tests d'intégration
-- Exécuté AVANT chaque méthode de test (BEFORE_TEST_METHOD par défaut)
-- La table employe existe déjà (créée par Hibernate via ddl-auto: create-drop)

-- Nettoyage des données existantes
DELETE FROM employe;

-- Reset de la séquence H2 pour recommencer à 1
ALTER TABLE employe ALTER COLUMN id RESTART WITH 1;

-- Insertion des 4 employés de test
INSERT INTO employe (prenom, nom, mail, adresse) VALUES
('Laurent', 'Martin', 'laurent.martin@example.com', '1 Rue de la Paix, Paris'),
('Sophie', 'Dubois', 'sophie.dubois@example.com', '2 Avenue des Champs, Lyon'),
('Pierre', 'Bernard', 'pierre.bernard@example.com', '3 Boulevard Victor Hugo, Marseille'),
('Marie', 'Durand', 'marie.durand@example.com', '4 Place de la République, Toulouse');
