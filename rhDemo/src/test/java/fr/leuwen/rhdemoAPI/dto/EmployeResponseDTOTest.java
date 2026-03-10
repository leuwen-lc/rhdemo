package fr.leuwen.rhdemoAPI.dto;

import static org.junit.jupiter.api.Assertions.*;

import org.junit.jupiter.api.Test;

import fr.leuwen.rhdemoAPI.model.Employe;

/**
 * Tests unitaires pour EmployeResponseDTO.
 * Vérifie le mapping depuis l'entité et les propriétés d'immutabilité du record.
 */
public class EmployeResponseDTOTest {

    // ════════════════════════════════════════════════════════════════
    // Tests from(Employe)
    // ════════════════════════════════════════════════════════════════

    @Test
    public void testFrom_ShouldMapAllFields() {
        Employe employe = new Employe();
        employe.setId(1L);
        employe.setPrenom("Jean");
        employe.setNom("Dupont");
        employe.setMail("jean.dupont@example.com");
        employe.setAdresse("123 Rue de Paris");

        EmployeResponseDTO dto = EmployeResponseDTO.from(employe);

        assertEquals(1L, dto.id());
        assertEquals("Jean", dto.prenom());
        assertEquals("Dupont", dto.nom());
        assertEquals("jean.dupont@example.com", dto.mail());
        assertEquals("123 Rue de Paris", dto.adresse());
    }

    @Test
    public void testFrom_WithNullAdresse_ShouldMapNull() {
        Employe employe = new Employe();
        employe.setId(2L);
        employe.setPrenom("Marie");
        employe.setNom("Martin");
        employe.setMail("marie.martin@example.com");
        employe.setAdresse(null);

        EmployeResponseDTO dto = EmployeResponseDTO.from(employe);

        assertEquals(2L, dto.id());
        assertNull(dto.adresse());
    }

    @Test
    public void testFrom_WithNullId_ShouldMapNull() {
        // Cas d'un employé non encore persisté (id non généré)
        Employe employe = new Employe();
        employe.setPrenom("Paul");
        employe.setNom("Durand");
        employe.setMail("paul.durand@example.com");

        EmployeResponseDTO dto = EmployeResponseDTO.from(employe);

        assertNull(dto.id());
        assertEquals("Paul", dto.prenom());
    }

    // ════════════════════════════════════════════════════════════════
    // Tests propriétés du record (equals, hashCode, immutabilité)
    // ════════════════════════════════════════════════════════════════

    @Test
    public void testEquals_SameValues_ShouldBeEqual() {
        EmployeResponseDTO dto1 = new EmployeResponseDTO(1L, "Jean", "Dupont", "jean@example.com", "Paris");
        EmployeResponseDTO dto2 = new EmployeResponseDTO(1L, "Jean", "Dupont", "jean@example.com", "Paris");

        assertEquals(dto1, dto2);
    }

    @Test
    public void testEquals_DifferentId_ShouldNotBeEqual() {
        EmployeResponseDTO dto1 = new EmployeResponseDTO(1L, "Jean", "Dupont", "jean@example.com", "Paris");
        EmployeResponseDTO dto2 = new EmployeResponseDTO(2L, "Jean", "Dupont", "jean@example.com", "Paris");

        assertNotEquals(dto1, dto2);
    }

    @Test
    public void testHashCode_SameValues_ShouldBeEqual() {
        EmployeResponseDTO dto1 = new EmployeResponseDTO(1L, "Jean", "Dupont", "jean@example.com", "Paris");
        EmployeResponseDTO dto2 = new EmployeResponseDTO(1L, "Jean", "Dupont", "jean@example.com", "Paris");

        assertEquals(dto1.hashCode(), dto2.hashCode());
    }

    @Test
    public void testToString_ShouldContainFieldValues() {
        EmployeResponseDTO dto = new EmployeResponseDTO(1L, "Jean", "Dupont", "jean@example.com", "Paris");

        String str = dto.toString();

        assertTrue(str.contains("Jean"));
        assertTrue(str.contains("Dupont"));
    }
}
