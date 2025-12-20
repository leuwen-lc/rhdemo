-- ═══════════════════════════════════════════════════════════════
-- Schéma de base de données pour RHDemo
-- DDL (Data Definition Language) - Définition des structures
-- ═══════════════════════════════════════════════════════════════

DROP TABLE IF EXISTS employes;

CREATE TABLE employes (
  id BIGSERIAL PRIMARY KEY,
  prenom VARCHAR(250) NOT NULL,
  nom VARCHAR(250) NOT NULL,
  mail VARCHAR(250) NOT NULL,
  adresse VARCHAR(500)
);

-- Création des index pour optimiser les performances
-- Index sur le mail pour les recherches rapides et l'unicité
CREATE UNIQUE INDEX idx_employes_mail ON employes(mail);

-- Index sur le nom pour les recherches alphabétiques
CREATE INDEX idx_employes_nom ON employes(nom);

-- Index sur le prénom pour les recherches par prénom
CREATE INDEX idx_employes_prenom ON employes(prenom);

-- Index composite sur nom + prénom pour les recherches combinées
CREATE INDEX idx_employes_nom_prenom ON employes(nom, prenom);

-- Index partiel sur l'adresse (seulement pour les adresses non-nulles)
-- Utile si beaucoup de recherches par ville/localisation
CREATE INDEX idx_employes_adresse ON employes(adresse) WHERE adresse IS NOT NULL;
