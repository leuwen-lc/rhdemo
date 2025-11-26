package fr.leuwen.rhdemoAPI.model;

import static org.junit.jupiter.api.Assertions.*;

import java.util.Set;

import jakarta.validation.ConstraintViolation;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import jakarta.validation.ValidatorFactory;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

/**
 * Tests unitaires pour les validations du modèle Employe
 * Vérifie que les contraintes @NotBlank, @Email, @Size fonctionnent correctement
 */
public class EmployeValidationTest {

    private Validator validator;

    @BeforeEach
    public void setUp() {
        ValidatorFactory factory = Validation.buildDefaultValidatorFactory();
        validator = factory.getValidator();
    }

    // ════════════════════════════════════════════════════════════════
    // Tests validation réussie
    // ════════════════════════════════════════════════════════════════

    @Test
    public void testValidEmploye_ShouldPassValidation() {
        // Arrange
        Employe employe = new Employe();
        employe.setPrenom("Jean");
        employe.setNom("Dupont");
        employe.setMail("jean.dupont@example.com");
        employe.setAdresse("123 Rue de Paris");

        // Act
        Set<ConstraintViolation<Employe>> violations = validator.validate(employe);

        // Assert
        assertTrue(violations.isEmpty(), "Un employé valide ne devrait avoir aucune violation");
    }

    // ════════════════════════════════════════════════════════════════
    // Tests @NotBlank sur prenom
    // ════════════════════════════════════════════════════════════════

    @Test
    public void testValidation_PrenomBlank_ShouldFail() {
        // Arrange
        Employe employe = new Employe();
        employe.setPrenom("");
        employe.setNom("Dupont");
        employe.setMail("jean.dupont@example.com");
        employe.setAdresse("123 Rue de Paris");

        // Act
        Set<ConstraintViolation<Employe>> violations = validator.validate(employe);

        // Assert
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream()
                .anyMatch(v -> v.getPropertyPath().toString().equals("prenom")));
    }

    @Test
    public void testValidation_PrenomNull_ShouldFail() {
        // Arrange
        Employe employe = new Employe();
        employe.setPrenom(null);
        employe.setNom("Dupont");
        employe.setMail("jean.dupont@example.com");
        employe.setAdresse("123 Rue de Paris");

        // Act
        Set<ConstraintViolation<Employe>> violations = validator.validate(employe);

        // Assert
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream()
                .anyMatch(v -> v.getPropertyPath().toString().equals("prenom")));
    }

    // ════════════════════════════════════════════════════════════════
    // Tests @NotBlank sur nom
    // ════════════════════════════════════════════════════════════════

    @Test
    public void testValidation_NomBlank_ShouldFail() {
        // Arrange
        Employe employe = new Employe();
        employe.setPrenom("Jean");
        employe.setNom("");
        employe.setMail("jean.dupont@example.com");
        employe.setAdresse("123 Rue de Paris");

        // Act
        Set<ConstraintViolation<Employe>> violations = validator.validate(employe);

        // Assert
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream()
                .anyMatch(v -> v.getPropertyPath().toString().equals("nom")));
    }

    // ════════════════════════════════════════════════════════════════
    // Tests @Email sur mail
    // ════════════════════════════════════════════════════════════════

    @Test
    public void testValidation_InvalidEmail_ShouldFail() {
        // Arrange
        Employe employe = new Employe();
        employe.setPrenom("Jean");
        employe.setNom("Dupont");
        employe.setMail("invalid-email");
        employe.setAdresse("123 Rue de Paris");

        // Act
        Set<ConstraintViolation<Employe>> violations = validator.validate(employe);

        // Assert
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream()
                .anyMatch(v -> v.getPropertyPath().toString().equals("mail")));
    }

    @Test
    public void testValidation_MailBlank_ShouldFail() {
        // Arrange
        Employe employe = new Employe();
        employe.setPrenom("Jean");
        employe.setNom("Dupont");
        employe.setMail("");
        employe.setAdresse("123 Rue de Paris");

        // Act
        Set<ConstraintViolation<Employe>> violations = validator.validate(employe);

        // Assert
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream()
                .anyMatch(v -> v.getPropertyPath().toString().equals("mail")));
    }

    // ════════════════════════════════════════════════════════════════
    // Tests @Size sur tous les champs
    // ════════════════════════════════════════════════════════════════

    @Test
    public void testValidation_PrenomTooLong_ShouldFail() {
        // Arrange
        String tooLongPrenom = "a".repeat(51); // Dépasse 50 caractères
        Employe employe = new Employe();
        employe.setPrenom(tooLongPrenom);
        employe.setNom("Dupont");
        employe.setMail("jean.dupont@example.com");
        employe.setAdresse("123 Rue de Paris");

        // Act
        Set<ConstraintViolation<Employe>> violations = validator.validate(employe);

        // Assert
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream()
                .anyMatch(v -> v.getPropertyPath().toString().equals("prenom")));
    }

    @Test
    public void testValidation_NomTooLong_ShouldFail() {
        // Arrange
        String tooLongNom = "a".repeat(51);
        Employe employe = new Employe();
        employe.setPrenom("Jean");
        employe.setNom(tooLongNom);
        employe.setMail("jean.dupont@example.com");
        employe.setAdresse("123 Rue de Paris");

        // Act
        Set<ConstraintViolation<Employe>> violations = validator.validate(employe);

        // Assert
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream()
                .anyMatch(v -> v.getPropertyPath().toString().equals("nom")));
    }

    @Test
    public void testValidation_MailTooLong_ShouldFail() {
        // Arrange
        String tooLongMail = "a".repeat(90) + "@example.com"; // > 50 caractères
        Employe employe = new Employe();
        employe.setPrenom("Jean");
        employe.setNom("Dupont");
        employe.setMail(tooLongMail);
        employe.setAdresse("123 Rue de Paris");

        // Act
        Set<ConstraintViolation<Employe>> violations = validator.validate(employe);

        // Assert
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream()
                .anyMatch(v -> v.getPropertyPath().toString().equals("mail")));
    }

    @Test
    public void testValidation_AdresseTooLong_ShouldFail() {
        // Arrange
        String tooLongAdresse = "a".repeat(201); // Dépasse 200 caractères
        Employe employe = new Employe();
        employe.setPrenom("Jean");
        employe.setNom("Dupont");
        employe.setMail("jean.dupont@example.com");
        employe.setAdresse(tooLongAdresse);

        // Act
        Set<ConstraintViolation<Employe>> violations = validator.validate(employe);

        // Assert
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream()
                .anyMatch(v -> v.getPropertyPath().toString().equals("adresse")));
    }

    // ════════════════════════════════════════════════════════════════
    // Tests limites (edge cases)
    // ════════════════════════════════════════════════════════════════

    @Test
    public void testValidation_PrenomExactly50Chars_ShouldPass() {
        // Arrange
        String exactLength = "a".repeat(50);
        Employe employe = new Employe();
        employe.setPrenom(exactLength);
        employe.setNom("Du");
        employe.setMail("jean.dupont@example.com");
        employe.setAdresse("123 Rue de Paris");

        // Act
        Set<ConstraintViolation<Employe>> violations = validator.validate(employe);

        // Assert
        assertTrue(violations.isEmpty(), "50 caractères devrait être accepté");
    }

    @Test
    public void testValidation_AdresseExactly200Chars_ShouldPass() {
        // Arrange
        String exactLength = "a".repeat(200);
        Employe employe = new Employe();
        employe.setPrenom("Jean");
        employe.setNom("Dupont");
        employe.setMail("jean.dupont@example.com");
        employe.setAdresse(exactLength);

        // Act
        Set<ConstraintViolation<Employe>> violations = validator.validate(employe);

        // Assert
        assertTrue(violations.isEmpty(), "200 caractères devrait être accepté");
    }

    @Test
    public void testValidation_MultipleViolations_ShouldReportAll() {
        // Arrange - Employé avec plusieurs erreurs
        Employe employe = new Employe();
        employe.setPrenom(""); // Blank
        employe.setNom(""); // Blank
        employe.setMail("invalid"); // Email invalide
        employe.setAdresse(""); // Blank

        // Act
        Set<ConstraintViolation<Employe>> violations = validator.validate(employe);

        // Assert
        assertTrue(violations.size() >= 4, "Devrait y avoir au moins 4 violations");
    }
}
