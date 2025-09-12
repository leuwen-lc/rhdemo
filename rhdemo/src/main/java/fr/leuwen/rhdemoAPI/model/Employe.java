package fr.leuwen.rhdemoAPI.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name="employes")
public class Employe {
@Id
@GeneratedValue(strategy=GenerationType.IDENTITY)
private Long id;
private String prenom;
private String nom;
private String mail;
@Column(name="mdp")
private String motdepasse;


public Long getId() {
	return id;
}
public void setId(Long id) {
	this.id = id;
}
public String getPrenom() {
	return prenom;
}
public void setPrenom(String prenom) {
	this.prenom = prenom;
}
public String getNom() {
	return nom;
}
public void setNom(String nom) {
	this.nom = nom;
}
public String getMail() {
	return mail;
}
public void setMail(String mail) {
	this.mail = mail;
}
public String getMotdepasse() {
	return motdepasse;
}
public void setMotdepasse(String motdepasse) {
	this.motdepasse = motdepasse;
}


}
