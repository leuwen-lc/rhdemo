package fr.leuwen.rhdemoAPI.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

@Entity
@Table(name="employes")
public class Employe {
@Id
@GeneratedValue(strategy=GenerationType.IDENTITY)
private Long id;

@NotBlank(message = "Le prénom est obligatoire")
@Size(min = 2, max = 50, message = "Le prénom doit contenir entre 2 et 50 caractères")
@Column(nullable = false, length = 50)
private String prenom;

@NotBlank(message = "Le nom est obligatoire")
@Size(min = 2, max = 50, message = "Le nom doit contenir entre 2 et 50 caractères")
@Column(nullable = false, length = 50)
private String nom;

@NotBlank(message = "L'email est obligatoire")
@Email(message = "L'email doit être valide")
@Size(max = 100, message = "L'email ne doit pas dépasser 100 caractères")
@Column(nullable = false, unique = true, length = 100)
private String mail;

@Size(max = 200, message = "L'adresse ne doit pas dépasser 200 caractères")
@Column(length = 200)
private String adresse;


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
public String getAdresse() {
	return adresse;
}
public void setAdresse(String adresse) {
	this.adresse = adresse;
}


}
