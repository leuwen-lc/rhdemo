package fr.leuwen.rhdemoAPI.controller;

import java.util.Optional;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import fr.leuwen.rhdemoAPI.model.Employe;
import fr.leuwen.rhdemoAPI.service.EmployeService;

@RestController
public class EmployeController {
    
    private static final Logger logger = LoggerFactory.getLogger(EmployeController.class);
    
	@Autowired
	private EmployeService employeservice;
	
	
	@GetMapping("/api/employes")
	@PreAuthorize("hasRole('consult')")
	public Iterable<Employe> getEmployes() {
		return employeservice.getEmployes();
	}
	
	/**
	 * Récupère une page d'employés avec pagination.
	 * 
	 * @param page Numéro de la page à récupérer (commence à 0). Par défaut : 0 (première page)
	 * @param size Nombre d'éléments par page. Par défaut : 20.
	 * @return Page<Employe> Objet contenant la liste des employés de la page demandée ainsi que 
	 *         les métadonnées de pagination (totalElements, totalPages, etc.)
	 * 
	 * Exemple d'utilisation :
	 * - GET /api/employes/page              → Première page avec 20 éléments
	 * - GET /api/employes/page?page=0       → Première page avec 20 éléments
	 * - GET /api/employes/page?page=2&size=50 → Troisième page avec 50 éléments
	 */
	@GetMapping("/api/employes/page")
	@PreAuthorize("hasRole('consult')")
	public Page<Employe> getEmployesPage(
			@RequestParam(defaultValue = "0") int page,
			@RequestParam(defaultValue = "20") int size) {
		Pageable pageable = PageRequest.of(page, size);
		return employeservice.getEmployesPage(pageable);
	}
	
	@GetMapping("/api/employe")
	@PreAuthorize("hasRole('consult')")
	public Optional<Employe> getEmploye(@RequestParam final Long id) {
		return employeservice.getEmploye(id);
	}
	
	@DeleteMapping("/api/employe")
	@PreAuthorize("hasRole('MAJ')")
	public void deleteEmploye(@RequestParam final Long id) {
	      employeservice.deleteEmploye(id);
	     
	}
	
	@PostMapping ("/api/employe")
	@PreAuthorize("hasRole('MAJ')")
	public Employe saveEmploye(@RequestBody Employe employe) {
	      logger.debug("=== RÉCEPTION DONNÉES EMPLOYE ===");
	      logger.debug("ID reçu: {}", employe.getId());
	      logger.debug("Prénom reçu: {}", employe.getPrenom());
	      logger.debug("Nom reçu: {}", employe.getNom());
	      logger.debug("Mail reçu: {}", employe.getMail());
	      logger.debug("Adresse reçue: {}", employe.getAdresse());
	      logger.info("Données employé validées, sauvegarde en cours...");
	      
	      Employe savedEmploye = employeservice.saveEmploye(employe);
	      logger.info("Employé sauvegardé avec succès - ID: {}", savedEmploye.getId());
	      return savedEmploye;
	}	

}
