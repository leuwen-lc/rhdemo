package fr.leuwen.rhdemoAPI.service;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.*;

import java.util.Arrays;
import java.util.Optional;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;

import fr.leuwen.rhdemoAPI.exception.EmployeNotFoundException;
import fr.leuwen.rhdemoAPI.model.Employe;
import fr.leuwen.rhdemoAPI.repository.EmployeRepository;

/**
 * Tests unitaires pour EmployeService
 * Utilise Mockito pour isoler la logique métier
 */
@ExtendWith(MockitoExtension.class)
public class EmployeServiceTest {

    @Mock
    private EmployeRepository employeRepository;

    @InjectMocks
    private EmployeService employeService;

    private Employe employe1;
    private Employe employe2;

    @BeforeEach
    public void setUp() {
        employe1 = new Employe();
        employe1.setId(1L);
        employe1.setPrenom("Jean");
        employe1.setNom("Dupont");
        employe1.setMail("jean.dupont@example.com");
        employe1.setAdresse("123 Rue de Paris");

        employe2 = new Employe();
        employe2.setId(2L);
        employe2.setPrenom("Marie");
        employe2.setNom("Martin");
        employe2.setMail("marie.martin@example.com");
        employe2.setAdresse("456 Avenue des Champs");
    }

    // ════════════════════════════════════════════════════════════════
    // Tests getEmploye(id)
    // ════════════════════════════════════════════════════════════════

    @Test
    public void testGetEmploye_WithValidId_ShouldReturnEmploye() {
        // Arrange
        when(employeRepository.findById(1L)).thenReturn(Optional.of(employe1));

        // Act
        Employe result = employeService.getEmploye(1L);

        // Assert
        assertNotNull(result);
        assertEquals(1L, result.getId());
        assertEquals("Jean", result.getPrenom());
        assertEquals("Dupont", result.getNom());
        verify(employeRepository, times(1)).findById(1L);
    }

    @Test
    public void testGetEmploye_WithInvalidId_ShouldThrowException() {
        // Arrange
        when(employeRepository.findById(999L)).thenReturn(Optional.empty());

        // Act & Assert
        EmployeNotFoundException exception = assertThrows(
                EmployeNotFoundException.class,
                () -> employeService.getEmploye(999L)
        );

        assertTrue(exception.getMessage().contains("999"));
        verify(employeRepository, times(1)).findById(999L);
    }

    // ════════════════════════════════════════════════════════════════
    // Tests getEmployes()
    // ════════════════════════════════════════════════════════════════

    @Test
    public void testGetEmployes_ShouldReturnAllEmployes() {
        // Arrange
        when(employeRepository.findAll()).thenReturn(Arrays.asList(employe1, employe2));

        // Act
        Iterable<Employe> result = employeService.getEmployes();

        // Assert
        assertNotNull(result);
        assertEquals(2, ((java.util.Collection<?>) result).size());
        verify(employeRepository, times(1)).findAll();
    }

    @Test
    public void testGetEmployes_WhenEmpty_ShouldReturnEmptyList() {
        // Arrange
        when(employeRepository.findAll()).thenReturn(Arrays.asList());

        // Act
        Iterable<Employe> result = employeService.getEmployes();

        // Assert
        assertNotNull(result);
        assertEquals(0, ((java.util.Collection<?>) result).size());
        verify(employeRepository, times(1)).findAll();
    }

    // ════════════════════════════════════════════════════════════════
    // Tests getEmployesPage(pageable)
    // ════════════════════════════════════════════════════════════════

    @Test
    public void testGetEmployesPage_ShouldReturnPage() {
        // Arrange
        Pageable pageable = PageRequest.of(0, 10);
        Page<Employe> expectedPage = new PageImpl<>(Arrays.asList(employe1, employe2));
        when(employeRepository.findAll(pageable)).thenReturn(expectedPage);

        // Act
        Page<Employe> result = employeService.getEmployesPage(pageable);

        // Assert
        assertNotNull(result);
        assertEquals(2, result.getContent().size());
        assertEquals(2, result.getTotalElements());
        verify(employeRepository, times(1)).findAll(pageable);
    }

    // ════════════════════════════════════════════════════════════════
    // Tests getEmployesPage(specification, pageable)
    // ════════════════════════════════════════════════════════════════

    @Test
    @SuppressWarnings("unchecked")
    public void testGetEmployesPageWithSpecification_ShouldReturnFilteredPage() {
        // Arrange
        Pageable pageable = PageRequest.of(0, 10);
        Specification<Employe> spec = mock(Specification.class);
        Page<Employe> expectedPage = new PageImpl<>(Arrays.asList(employe1));
        when(employeRepository.findAll(eq(spec), eq(pageable))).thenReturn(expectedPage);

        // Act
        Page<Employe> result = employeService.getEmployesPage(spec, pageable);

        // Assert
        assertNotNull(result);
        assertEquals(1, result.getContent().size());
        assertEquals(1, result.getTotalElements());
        assertEquals("Jean", result.getContent().get(0).getPrenom());
        verify(employeRepository, times(1)).findAll(eq(spec), eq(pageable));
    }

    // ════════════════════════════════════════════════════════════════
    // Tests deleteEmploye(id)
    // ════════════════════════════════════════════════════════════════

    @Test
    public void testDeleteEmploye_WithValidId_ShouldDeleteSuccessfully() {
        // Arrange
        when(employeRepository.existsById(1L)).thenReturn(true);
        doNothing().when(employeRepository).deleteById(1L);

        // Act
        employeService.deleteEmploye(1L);

        // Assert
        verify(employeRepository, times(1)).existsById(1L);
        verify(employeRepository, times(1)).deleteById(1L);
    }

    @Test
    public void testDeleteEmploye_WithInvalidId_ShouldThrowException() {
        // Arrange
        when(employeRepository.existsById(999L)).thenReturn(false);

        // Act & Assert
        EmployeNotFoundException exception = assertThrows(
                EmployeNotFoundException.class,
                () -> employeService.deleteEmploye(999L)
        );

        assertTrue(exception.getMessage().contains("999"));
        verify(employeRepository, times(1)).existsById(999L);
        verify(employeRepository, never()).deleteById(any());
    }

    // ════════════════════════════════════════════════════════════════
    // Tests saveEmploye(employe)
    // ════════════════════════════════════════════════════════════════

    @Test
    public void testSaveEmploye_WithNewEmploye_ShouldSaveSuccessfully() {
        // Arrange
        Employe newEmploye = new Employe();
        newEmploye.setPrenom("Paul");
        newEmploye.setNom("Durand");
        newEmploye.setMail("paul.durand@example.com");
        newEmploye.setAdresse("789 Boulevard Victor Hugo");

        Employe savedEmploye = new Employe();
        savedEmploye.setId(3L);
        savedEmploye.setPrenom("Paul");
        savedEmploye.setNom("Durand");
        savedEmploye.setMail("paul.durand@example.com");
        savedEmploye.setAdresse("789 Boulevard Victor Hugo");

        when(employeRepository.save(newEmploye)).thenReturn(savedEmploye);

        // Act
        Employe result = employeService.saveEmploye(newEmploye);

        // Assert
        assertNotNull(result);
        assertEquals(3L, result.getId());
        assertEquals("Paul", result.getPrenom());
        verify(employeRepository, times(1)).save(newEmploye);
    }

    @Test
    public void testSaveEmploye_WithExistingEmploye_ShouldUpdateSuccessfully() {
        // Arrange
        employe1.setPrenom("Jean-Updated");
        when(employeRepository.save(employe1)).thenReturn(employe1);

        // Act
        Employe result = employeService.saveEmploye(employe1);

        // Assert
        assertNotNull(result);
        assertEquals(1L, result.getId());
        assertEquals("Jean-Updated", result.getPrenom());
        verify(employeRepository, times(1)).save(employe1);
    }
}
