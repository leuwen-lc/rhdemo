package fr.leuwen.rhdemoAPI.dto;

import static org.junit.jupiter.api.Assertions.*;

import java.util.Set;

import jakarta.validation.ConstraintViolation;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import jakarta.validation.ValidatorFactory;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import fr.leuwen.rhdemoAPI.model.Employe;

/**
 * Tests unitaires pour les validations de EmployeRequestDTO.
 * Vérifie que les contraintes @NotBlank, @Email, @Size fonctionnent correctement
 * sur le DTO d'entrée, et que toEmploye() produit une entité correcte.
 */
public class EmployeRequestDTOTest {

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
    public void testValidDTO_ShouldPassValidation() {
        EmployeRequestDTO dto = new EmployeRequestDTO("Jean", "Dupont", "jean.dupont@example.com", "123 Rue de Paris");

        Set<ConstraintViolation<EmployeRequestDTO>> violations = validator.validate(dto);

        assertTrue(violations.isEmpty(), "Un DTO valide ne devrait avoir aucune violation");
    }

    @Test
    public void testValidDTO_WithNullAdresse_ShouldPassValidation() {
        EmployeRequestDTO dto = new EmployeRequestDTO("Jean", "Dupont", "jean.dupont@example.com", null);

        Set<ConstraintViolation<EmployeRequestDTO>> violations = validator.validate(dto);

        assertTrue(violations.isEmpty(), "L'adresse est optionnelle");
    }

    // ════════════════════════════════════════════════════════════════
    // Tests @NotBlank sur prenom
    // ════════════════════════════════════════════════════════════════

    @Test
    public void testValidation_PrenomBlank_ShouldFail() {
        EmployeRequestDTO dto = new EmployeRequestDTO("", "Dupont", "jean.dupont@example.com", "Paris");

        Set<ConstraintViolation<EmployeRequestDTO>> violations = validator.validate(dto);

        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("prenom")));
    }

    @Test
    public void testValidation_PrenomNull_ShouldFail() {
        EmployeRequestDTO dto = new EmployeRequestDTO(null, "Dupont", "jean.dupont@example.com", "Paris");

        Set<ConstraintViolation<EmployeRequestDTO>> violations = validator.validate(dto);

        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("prenom")));
    }

    // ════════════════════════════════════════════════════════════════
    // Tests @NotBlank sur nom
    // ════════════════════════════════════════════════════════════════

    @Test
    public void testValidation_NomBlank_ShouldFail() {
        EmployeRequestDTO dto = new EmployeRequestDTO("Jean", "", "jean.dupont@example.com", "Paris");

        Set<ConstraintViolation<EmployeRequestDTO>> violations = validator.validate(dto);

        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("nom")));
    }

    // ════════════════════════════════════════════════════════════════
    // Tests @Email sur mail
    // ════════════════════════════════════════════════════════════════

    @Test
    public void testValidation_InvalidEmail_ShouldFail() {
        EmployeRequestDTO dto = new EmployeRequestDTO("Jean", "Dupont", "invalid-email", "Paris");

        Set<ConstraintViolation<EmployeRequestDTO>> violations = validator.validate(dto);

        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("mail")));
    }

    @Test
    public void testValidation_MailBlank_ShouldFail() {
        EmployeRequestDTO dto = new EmployeRequestDTO("Jean", "Dupont", "", "Paris");

        Set<ConstraintViolation<EmployeRequestDTO>> violations = validator.validate(dto);

        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("mail")));
    }

    // ════════════════════════════════════════════════════════════════
    // Tests @Size sur tous les champs
    // ════════════════════════════════════════════════════════════════

    @Test
    public void testValidation_PrenomTooLong_ShouldFail() {
        EmployeRequestDTO dto = new EmployeRequestDTO("a".repeat(51), "Dupont", "jean.dupont@example.com", "Paris");

        Set<ConstraintViolation<EmployeRequestDTO>> violations = validator.validate(dto);

        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("prenom")));
    }

    @Test
    public void testValidation_NomTooLong_ShouldFail() {
        EmployeRequestDTO dto = new EmployeRequestDTO("Jean", "a".repeat(51), "jean.dupont@example.com", "Paris");

        Set<ConstraintViolation<EmployeRequestDTO>> violations = validator.validate(dto);

        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("nom")));
    }

    @Test
    public void testValidation_MailTooLong_ShouldFail() {
        String tooLongMail = "a".repeat(90) + "@example.com";
        EmployeRequestDTO dto = new EmployeRequestDTO("Jean", "Dupont", tooLongMail, "Paris");

        Set<ConstraintViolation<EmployeRequestDTO>> violations = validator.validate(dto);

        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("mail")));
    }

    @Test
    public void testValidation_AdresseTooLong_ShouldFail() {
        EmployeRequestDTO dto = new EmployeRequestDTO("Jean", "Dupont", "jean.dupont@example.com", "a".repeat(201));

        Set<ConstraintViolation<EmployeRequestDTO>> violations = validator.validate(dto);

        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("adresse")));
    }

    // ════════════════════════════════════════════════════════════════
    // Tests limites (edge cases)
    // ════════════════════════════════════════════════════════════════

    @Test
    public void testValidation_PrenomExactly50Chars_ShouldPass() {
        EmployeRequestDTO dto = new EmployeRequestDTO("a".repeat(50), "Du", "jean.dupont@example.com", "Paris");

        Set<ConstraintViolation<EmployeRequestDTO>> violations = validator.validate(dto);

        assertTrue(violations.isEmpty(), "50 caractères devrait être accepté");
    }

    @Test
    public void testValidation_AdresseExactly200Chars_ShouldPass() {
        EmployeRequestDTO dto = new EmployeRequestDTO("Jean", "Dupont", "jean.dupont@example.com", "a".repeat(200));

        Set<ConstraintViolation<EmployeRequestDTO>> violations = validator.validate(dto);

        assertTrue(violations.isEmpty(), "200 caractères devrait être accepté");
    }

    @Test
    public void testValidation_MultipleViolations_ShouldReportAll() {
        EmployeRequestDTO dto = new EmployeRequestDTO("", "", "invalid", "");

        Set<ConstraintViolation<EmployeRequestDTO>> violations = validator.validate(dto);

        assertTrue(violations.size() >= 4, "Devrait y avoir au moins 4 violations");
    }

    // ════════════════════════════════════════════════════════════════
    // Tests toEmploye()
    // ════════════════════════════════════════════════════════════════

    @Test
    public void testToEmploye_ShouldMapAllFields() {
        EmployeRequestDTO dto = new EmployeRequestDTO("Jean", "Dupont", "jean.dupont@example.com", "123 Rue de Paris");

        Employe employe = dto.toEmploye();

        assertNull(employe.getId(), "L'id doit être null : généré par la base pour CREATE, fourni par le path pour UPDATE");
        assertEquals("Jean", employe.getPrenom());
        assertEquals("Dupont", employe.getNom());
        assertEquals("jean.dupont@example.com", employe.getMail());
        assertEquals("123 Rue de Paris", employe.getAdresse());
    }

    @Test
    public void testToEmploye_WithNullAdresse_ShouldMapNull() {
        EmployeRequestDTO dto = new EmployeRequestDTO("Jean", "Dupont", "jean.dupont@example.com", null);

        Employe employe = dto.toEmploye();

        assertNull(employe.getAdresse());
    }
}
