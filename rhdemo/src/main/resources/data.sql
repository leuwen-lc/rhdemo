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