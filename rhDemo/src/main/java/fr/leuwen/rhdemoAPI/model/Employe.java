package fr.leuwen.rhdemoAPI.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import org.jspecify.annotations.NonNull;
import org.jspecify.annotations.Nullable;

/**
 * Entité JPA Employe.
 * Les contraintes de forme (NotBlank, Email, Size) sont dans EmployeRequestDTO.
 * Les contraintes @Column garantissent l'intégrité au niveau base de données.
 */
@Entity
@Table(name="employes")
public class Employe {

    @Id
    @GeneratedValue(strategy=GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 50)
    private @NonNull String prenom;

    @Column(nullable = false, length = 50)
    private @NonNull String nom;

    @Column(nullable = false, unique = true, length = 100)
    private @NonNull String mail;

    @Column(length = 200)
    private @Nullable String adresse;


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
