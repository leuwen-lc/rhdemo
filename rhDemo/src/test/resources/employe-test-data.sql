-- Données de test pour les tests d'intégration
-- Nettoyage et insertion des données de test

DELETE FROM employe;

-- Reset de la séquence H2 pour recommencer à 1
ALTER TABLE employe ALTER COLUMN id RESTART WITH 1;

INSERT INTO employe (prenom, nom, mail, adresse) VALUES
('Laurent', 'Martin', 'laurent.martin@example.com', '1 Rue de la Paix, Paris'),
('Sophie', 'Dubois', 'sophie.dubois@example.com', '2 Avenue des Champs, Lyon'),
('Pierre', 'Bernard', 'pierre.bernard@example.com', '3 Boulevard Victor Hugo, Marseille'),
('Marie', 'Durand', 'marie.durand@example.com', '4 Place de la République, Toulouse');
