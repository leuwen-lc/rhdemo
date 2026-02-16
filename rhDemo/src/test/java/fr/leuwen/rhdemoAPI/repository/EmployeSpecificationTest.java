package fr.leuwen.rhdemoAPI.repository;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.test.context.ActiveProfiles;
import fr.leuwen.rhdemoAPI.model.Employe;

/**
 * Tests unitaires pour EmployeSpecification.
 * Utilise @DataJpaTest avec H2 pour tester les Specifications JPA.
 */
@DataJpaTest
@ActiveProfiles("test")
class EmployeSpecificationTest {

    @Autowired
    private EmployeRepository employeRepository;

    @BeforeEach
    void setUp() {
        employeRepository.deleteAll();

        Employe emp1 = new Employe();
        emp1.setPrenom("Laurent");
        emp1.setNom("Martin");
        emp1.setMail("laurent.martin@example.com");
        emp1.setAdresse("1 Rue de la Paix, Paris");
        employeRepository.save(emp1);

        Employe emp2 = new Employe();
        emp2.setPrenom("Sophie");
        emp2.setNom("Dubois");
        emp2.setMail("sophie.dubois@example.com");
        emp2.setAdresse("2 Avenue des Champs, Lyon");
        employeRepository.save(emp2);

        Employe emp3 = new Employe();
        emp3.setPrenom("Pierre");
        emp3.setNom("Bernard");
        emp3.setMail("pierre.bernard@example.com");
        emp3.setAdresse("3 Boulevard Victor Hugo, Marseille");
        employeRepository.save(emp3);
    }

    // ════════════════════════════════════════════════════════════════
    // Tests avec tous les filtres null ou vides (aucun filtre actif)
    // ════════════════════════════════════════════════════════════════

    @Test
    void withFilters_AllNull_ShouldReturnAllEmployes() {
        Specification<Employe> spec = EmployeSpecification.withFilters(null, null, null, null);

        List<Employe> result = employeRepository.findAll(spec);

        assertThat(result).hasSize(3);
    }

    @Test
    void withFilters_AllBlank_ShouldReturnAllEmployes() {
        Specification<Employe> spec = EmployeSpecification.withFilters("", "", "", "");

        List<Employe> result = employeRepository.findAll(spec);

        assertThat(result).hasSize(3);
    }

    @Test
    void withFilters_AllWhitespace_ShouldReturnAllEmployes() {
        Specification<Employe> spec = EmployeSpecification.withFilters("  ", "  ", "  ", "  ");

        List<Employe> result = employeRepository.findAll(spec);

        assertThat(result).hasSize(3);
    }

    // ════════════════════════════════════════════════════════════════
    // Tests avec un seul filtre actif
    // ════════════════════════════════════════════════════════════════

    @Test
    void withFilters_ByPrenom_ShouldReturnMatchingEmployes() {
        Specification<Employe> spec = EmployeSpecification.withFilters("Laurent", null, null, null);

        List<Employe> result = employeRepository.findAll(spec);

        assertThat(result).hasSize(1);
        assertThat(result.get(0).getPrenom()).isEqualTo("Laurent");
    }

    @Test
    void withFilters_ByNom_ShouldReturnMatchingEmployes() {
        Specification<Employe> spec = EmployeSpecification.withFilters(null, "Martin", null, null);

        List<Employe> result = employeRepository.findAll(spec);

        assertThat(result).hasSize(1);
        assertThat(result.get(0).getNom()).isEqualTo("Martin");
    }

    @Test
    void withFilters_ByMail_ShouldReturnMatchingEmployes() {
        Specification<Employe> spec = EmployeSpecification.withFilters(null, null, "sophie", null);

        List<Employe> result = employeRepository.findAll(spec);

        assertThat(result).hasSize(1);
        assertThat(result.get(0).getMail()).isEqualTo("sophie.dubois@example.com");
    }

    @Test
    void withFilters_ByAdresse_ShouldReturnMatchingEmployes() {
        Specification<Employe> spec = EmployeSpecification.withFilters(null, null, null, "Paris");

        List<Employe> result = employeRepository.findAll(spec);

        assertThat(result).hasSize(1);
        assertThat(result.get(0).getAdresse()).contains("Paris");
    }

    // ════════════════════════════════════════════════════════════════
    // Tests de recherche insensible à la casse
    // ════════════════════════════════════════════════════════════════

    @Test
    void withFilters_CaseInsensitive_ShouldMatch() {
        Specification<Employe> spec = EmployeSpecification.withFilters("LAURENT", null, null, null);

        List<Employe> result = employeRepository.findAll(spec);

        assertThat(result).hasSize(1);
        assertThat(result.get(0).getPrenom()).isEqualTo("Laurent");
    }

    // ════════════════════════════════════════════════════════════════
    // Tests de recherche partielle
    // ════════════════════════════════════════════════════════════════

    @Test
    void withFilters_PartialMatch_ShouldReturnMatchingEmployes() {
        Specification<Employe> spec = EmployeSpecification.withFilters(null, "ub", null, null);

        List<Employe> result = employeRepository.findAll(spec);

        assertThat(result).hasSize(1);
        assertThat(result.get(0).getNom()).isEqualTo("Dubois");
    }

    // ════════════════════════════════════════════════════════════════
    // Tests avec plusieurs filtres combinés (AND)
    // ════════════════════════════════════════════════════════════════

    @Test
    void withFilters_CombinedFilters_ShouldReturnIntersection() {
        Specification<Employe> spec = EmployeSpecification.withFilters("Sophie", "Dubois", null, null);

        List<Employe> result = employeRepository.findAll(spec);

        assertThat(result).hasSize(1);
        assertThat(result.get(0).getPrenom()).isEqualTo("Sophie");
    }

    @Test
    void withFilters_AllFiltersCombined_ShouldReturnMatchingEmploye() {
        Specification<Employe> spec = EmployeSpecification.withFilters("Pierre", "Bernard", "pierre", "Marseille");

        List<Employe> result = employeRepository.findAll(spec);

        assertThat(result).hasSize(1);
        assertThat(result.get(0).getPrenom()).isEqualTo("Pierre");
    }

    @Test
    void withFilters_ConflictingFilters_ShouldReturnEmpty() {
        Specification<Employe> spec = EmployeSpecification.withFilters("Laurent", "Dubois", null, null);

        List<Employe> result = employeRepository.findAll(spec);

        assertThat(result).isEmpty();
    }

    // ════════════════════════════════════════════════════════════════
    // Tests sans résultat
    // ════════════════════════════════════════════════════════════════

    @Test
    void withFilters_NoMatch_ShouldReturnEmpty() {
        Specification<Employe> spec = EmployeSpecification.withFilters("Inexistant", null, null, null);

        List<Employe> result = employeRepository.findAll(spec);

        assertThat(result).isEmpty();
    }

    // ════════════════════════════════════════════════════════════════
    // Tests avec filtres mixtes (certains null, certains remplis)
    // ════════════════════════════════════════════════════════════════

    @Test
    void withFilters_MixedNullAndValues_ShouldOnlyApplyNonNullFilters() {
        Specification<Employe> spec = EmployeSpecification.withFilters(null, "Bernard", "", null);

        List<Employe> result = employeRepository.findAll(spec);

        assertThat(result).hasSize(1);
        assertThat(result.get(0).getNom()).isEqualTo("Bernard");
    }
}
