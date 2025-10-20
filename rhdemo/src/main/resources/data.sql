DROP TABLE IF EXISTS employes;
 
CREATE TABLE employes (
  id BIGINT AUTO_INCREMENT  PRIMARY KEY,
  prenom VARCHAR(250) NOT NULL,
  nom VARCHAR(250) NOT NULL,
  mail VARCHAR(250) NOT NULL,
  adresse VARCHAR(500) NOT NULL
);
 
INSERT INTO employes (prenom, nom, mail, adresse) VALUES
  ('Laurent', 'GINA', 'laurentgina@mail.com', '123 Rue de la Paix, 75001 Paris'),
  ('Sophie', 'FONCEK', 'sophiefoncek@mail.com', '456 Avenue des Champs, 69000 Lyon'),
  ('Agathe', 'FEELING', 'agathefeeling@mail.com', '789 Boulevard Central, 13000 Marseille');
  

DROP TABLE IF EXISTS dbuser;
CREATE TABLE dbuser (
  id INT AUTO_INCREMENT  PRIMARY KEY,
  username VARCHAR(250) NOT NULL,
  password VARCHAR(250) NOT NULL,
  role VARCHAR(250) NOT NULL
);

INSERT INTO dbuser (username, password, role) VALUES 
('Madjid', 'Pass', 'MAJ'),
('Constance', 'Pass', 'Consult'),
('Adele', 'Pass', 'Admin');