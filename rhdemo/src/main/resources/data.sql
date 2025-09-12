DROP TABLE IF EXISTS employes;
 
CREATE TABLE employes (
  id BIGINT AUTO_INCREMENT  PRIMARY KEY,
  prenom VARCHAR(250) NOT NULL,
  nom VARCHAR(250) NOT NULL,
  mail VARCHAR(250) NOT NULL,
  mdp VARCHAR(250) NOT NULL
);
 
INSERT INTO employes (prenom, nom, mail, mdp) VALUES
  ('Laurent', 'GINA', 'laurentgina@mail.com', 'laurent'),
  ('Sophie', 'FONCEK', 'sophiefoncek@mail.com', 'sophie'),
  ('Agathe', 'FEELING', 'agathefeeling@mail.com', 'agathe');