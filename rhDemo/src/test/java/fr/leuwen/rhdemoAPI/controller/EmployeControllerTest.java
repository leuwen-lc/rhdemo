package fr.leuwen.rhdemoAPI.controller;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

import java.util.Arrays;
import java.util.List;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;

import fr.leuwen.rhdemoAPI.model.Employe;
import fr.leuwen.rhdemoAPI.service.EmployeService;

/**
 * Tests unitaires pour EmployeController.
 * Teste la logique du contrôleur (tri, pagination, filtres) sans contexte Spring.
 */
@ExtendWith(MockitoExtension.class)
class EmployeControllerTest {

    @Mock
    private EmployeService employeService;

    @InjectMocks
    private EmployeController controller;

    private Employe employe1;

    @BeforeEach
    void setUp() {
        employe1 = new Employe();
        employe1.setId(1L);
        employe1.setPrenom("Jean");
        employe1.setNom("Dupont");
        employe1.setMail("jean.dupont@example.com");
        employe1.setAdresse("123 Rue de Paris");
    }

    // ════════════════════════════════════════════════════════════════
    // Tests getEmployesPage (pagination avec tri et filtres)
    // ════════════════════════════════════════════════════════════════

    @Test
    @SuppressWarnings("unchecked")
    void getEmployesPage_WithSort_ShouldCreateSortedPageable() {
        Page<Employe> expectedPage = new PageImpl<>(List.of(employe1));
        when(employeService.getEmployesPage(any(Specification.class), any(Pageable.class)))
                .thenReturn(expectedPage);

        Page<Employe> result = controller.getEmployesPage(0, 20, "nom", "ASC",
                null, null, null, null);

        assertNotNull(result);
        assertEquals(1, result.getTotalElements());

        ArgumentCaptor<Pageable> pageableCaptor = ArgumentCaptor.forClass(Pageable.class);
        verify(employeService).getEmployesPage(any(Specification.class), pageableCaptor.capture());
        Pageable captured = pageableCaptor.getValue();
        assertTrue(captured.getSort().isSorted());
        assertEquals("nom", captured.getSort().iterator().next().getProperty());
        assertTrue(captured.getSort().iterator().next().isAscending());
    }

    @Test
    @SuppressWarnings("unchecked")
    void getEmployesPage_WithSortDesc_ShouldCreateDescendingPageable() {
        Page<Employe> expectedPage = new PageImpl<>(List.of(employe1));
        when(employeService.getEmployesPage(any(Specification.class), any(Pageable.class)))
                .thenReturn(expectedPage);

        controller.getEmployesPage(0, 10, "prenom", "DESC",
                null, null, null, null);

        ArgumentCaptor<Pageable> pageableCaptor = ArgumentCaptor.forClass(Pageable.class);
        verify(employeService).getEmployesPage(any(Specification.class), pageableCaptor.capture());
        Pageable captured = pageableCaptor.getValue();
        assertTrue(captured.getSort().iterator().next().isDescending());
    }

    @Test
    @SuppressWarnings("unchecked")
    void getEmployesPage_WithoutSort_ShouldCreateUnsortedPageable() {
        Page<Employe> expectedPage = new PageImpl<>(List.of(employe1));
        when(employeService.getEmployesPage(any(Specification.class), any(Pageable.class)))
                .thenReturn(expectedPage);

        controller.getEmployesPage(0, 20, null, "ASC",
                null, null, null, null);

        ArgumentCaptor<Pageable> pageableCaptor = ArgumentCaptor.forClass(Pageable.class);
        verify(employeService).getEmployesPage(any(Specification.class), pageableCaptor.capture());
        Pageable captured = pageableCaptor.getValue();
        assertTrue(captured.getSort().isUnsorted());
    }

    // ════════════════════════════════════════════════════════════════
    // Tests getEmployes (liste complète)
    // ════════════════════════════════════════════════════════════════

    @Test
    void getEmployes_ShouldDelegateToService() {
        when(employeService.getEmployes()).thenReturn(Arrays.asList(employe1));

        Iterable<Employe> result = controller.getEmployes();

        assertNotNull(result);
        verify(employeService).getEmployes();
    }

    // ════════════════════════════════════════════════════════════════
    // Tests getEmploye (récupération par ID)
    // ════════════════════════════════════════════════════════════════

    @Test
    void getEmploye_ShouldDelegateToService() {
        when(employeService.getEmploye(1L)).thenReturn(employe1);

        Employe result = controller.getEmploye(1L);

        assertEquals(1L, result.getId());
        verify(employeService).getEmploye(1L);
    }

    // ════════════════════════════════════════════════════════════════
    // Tests saveEmploye
    // ════════════════════════════════════════════════════════════════

    @Test
    void saveEmploye_ShouldDelegateToService() {
        when(employeService.saveEmploye(employe1)).thenReturn(employe1);

        Employe result = controller.saveEmploye(employe1);

        assertEquals(1L, result.getId());
        verify(employeService).saveEmploye(employe1);
    }

    // ════════════════════════════════════════════════════════════════
    // Tests deleteEmploye
    // ════════════════════════════════════════════════════════════════

    @Test
    void deleteEmploye_ShouldDelegateToService() {
        doNothing().when(employeService).deleteEmploye(1L);

        controller.deleteEmploye(1L);

        verify(employeService).deleteEmploye(1L);
    }
}
