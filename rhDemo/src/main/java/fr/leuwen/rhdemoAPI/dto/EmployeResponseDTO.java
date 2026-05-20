package fr.leuwen.rhdemoAPI.dto;

import java.util.Objects;

import fr.leuwen.rhdemoAPI.model.Employe;

/**
 * DTO immuable (record) pour les réponses API.
 * Découple le contrat API de l'entité JPA : tout champ interne ajouté à Employe
 * n'est pas exposé automatiquement côté client.
 */
public record EmployeResponseDTO(Long id, String prenom, String nom, String mail, String adresse) {

    public static EmployeResponseDTO from(Employe employe) {
        Objects.requireNonNull(employe, "employe ne peut pas être null");
        return new EmployeResponseDTO(
                employe.getId(),
                employe.getPrenom(),
                employe.getNom(),
                employe.getMail(),
                employe.getAdresse()
        );
    }
}
