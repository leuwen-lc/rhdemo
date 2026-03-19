package fr.leuwen.rhdemoAPI.dto;

import fr.leuwen.rhdemoAPI.model.Employe;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * DTO immuable (record) pour les requêtes API en entrée (POST et PUT).
 * Aucun champ id : l'identifiant provient exclusivement du chemin URL pour PUT,
 * et est généré par la base pour POST.
 * Les contraintes Bean Validation sont ici, pas sur l'entité JPA.
 */
public record EmployeRequestDTO(

        @NotBlank(message = "Le prénom est obligatoire")
        @Size(min = 2, max = 50, message = "Le prénom doit contenir entre 2 et 50 caractères")
        String prenom,

        @NotBlank(message = "Le nom est obligatoire")
        @Size(min = 2, max = 50, message = "Le nom doit contenir entre 2 et 50 caractères")
        String nom,

        @NotBlank(message = "L'email est obligatoire")
        @Email(message = "L'email doit être valide")
        @Size(max = 100, message = "L'email ne doit pas dépasser 100 caractères")
        String mail,

        @Size(max = 200, message = "L'adresse ne doit pas dépasser 200 caractères")
        String adresse

) {
    public Employe toEmploye() {
        Employe employe = new Employe();
        employe.setPrenom(this.prenom);
        employe.setNom(this.nom);
        employe.setMail(this.mail);
        employe.setAdresse(this.adresse);
        return employe;
    }
}
