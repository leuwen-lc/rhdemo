package fr.leuwen.rhdemoAPI.controller;

import java.util.List;
import java.util.stream.StreamSupport;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import fr.leuwen.rhdemoAPI.dto.EmployeRequestDTO;
import fr.leuwen.rhdemoAPI.dto.EmployeResponseDTO;
import fr.leuwen.rhdemoAPI.model.Employe;
import fr.leuwen.rhdemoAPI.repository.EmployeSpecification;
import fr.leuwen.rhdemoAPI.service.EmployeService;
import jakarta.validation.Valid;

@RestController
public class EmployeController {

    private static final Logger logger = LoggerFactory.getLogger(EmployeController.class);

	private final EmployeService employeservice;

	//Autowired par défaut avec Spring Boot
	public EmployeController(EmployeService employeservice) {
		this.employeservice = employeservice;
	}
	
	
	@GetMapping("/api/employes")
	@PreAuthorize("hasRole('consult')")
	public List<EmployeResponseDTO> getEmployes() {
		return StreamSupport.stream(employeservice.getEmployes().spliterator(), false)
				.map(EmployeResponseDTO::from)
				.toList();
	}
	
	/**
	 * Récupère une page d'employés avec pagination, tri optionnel et filtres optionnels.
	 *
	 * @param page Numéro de la page à récupérer (commence à 0). Par défaut : 0 (première page)
	 * @param size Nombre d'éléments par page. Par défaut : 20.
	 * @param sort Nom de la colonne pour le tri (prenom, nom, mail, adresse). Optionnel.
	 * @param order Direction du tri : ASC (ascendant) ou DESC (descendant). Par défaut : ASC.
	 * @param filterPrenom Filtre sur le prénom (recherche partielle insensible à la casse). Optionnel.
	 * @param filterNom Filtre sur le nom (recherche partielle insensible à la casse). Optionnel.
	 * @param filterMail Filtre sur l'email (recherche partielle insensible à la casse). Optionnel.
	 * @param filterAdresse Filtre sur l'adresse (recherche partielle insensible à la casse). Optionnel.
	 * @return Page<Employe> Objet contenant la liste des employés de la page demandée ainsi que
	 *         les métadonnées de pagination (totalElements, totalPages, etc.)
	 *
	 * Exemple d'utilisation :
	 * - GET /api/employes/page                           → Première page avec 20 éléments, sans tri
	 * - GET /api/employes/page?page=0                    → Première page avec 20 éléments, sans tri
	 * - GET /api/employes/page?page=2&size=50            → Troisième page avec 50 éléments, sans tri
	 * - GET /api/employes/page?sort=nom&order=ASC        → Première page triée par nom ascendant
	 * - GET /api/employes/page?sort=prenom&order=DESC    → Première page triée par prénom descendant
	 * - GET /api/employes/page?filterNom=Martin          → Employés dont le nom contient "Martin"
	 * - GET /api/employes/page?filterPrenom=So&filterNom=Du → Filtres combinés (AND)
	 */
	@GetMapping("/api/employes/page")
	@PreAuthorize("hasRole('consult')")
	public Page<EmployeResponseDTO> getEmployesPage(
			@RequestParam(defaultValue = "0") int page,
			@RequestParam(defaultValue = "20") int size,
			@RequestParam(required = false) String sort,
			@RequestParam(defaultValue = "ASC") String order,
			@RequestParam(required = false) String filterPrenom,
			@RequestParam(required = false) String filterNom,
			@RequestParam(required = false) String filterMail,
			@RequestParam(required = false) String filterAdresse) {

		Pageable pageable;
		if (sort != null && !sort.isEmpty()) {
			Sort.Direction direction = "DESC".equalsIgnoreCase(order) ? Sort.Direction.DESC : Sort.Direction.ASC;
			pageable = PageRequest.of(page, size, Sort.by(direction, sort));
		} else {
			pageable = PageRequest.of(page, size);
		}

		Specification<Employe> spec = EmployeSpecification.withFilters(filterPrenom, filterNom, filterMail, filterAdresse);
		return employeservice.getEmployesPage(spec, pageable).map(EmployeResponseDTO::from);
	}

	@GetMapping("/api/employe")
	@PreAuthorize("hasRole('consult')")
	public EmployeResponseDTO getEmploye(@RequestParam final Long id) {
		return EmployeResponseDTO.from(employeservice.getEmploye(id));
	}
	
	@DeleteMapping("/api/employe/{id}")
	@PreAuthorize("hasRole('MAJ')")
	@ResponseStatus(HttpStatus.NO_CONTENT)
	public void deleteEmploye(@PathVariable final Long id) {
		employeservice.deleteEmploye(id);
	}

	@PostMapping("/api/employe")
	@PreAuthorize("hasRole('MAJ')")
	@ResponseStatus(HttpStatus.CREATED)
	public EmployeResponseDTO createEmploye(@Valid @RequestBody EmployeRequestDTO dto) {
		logger.debug("Création employé - prénom: {}, nom: {}", dto.prenom(), dto.nom());
		logger.info("Données employé validées, création en cours...");
		EmployeResponseDTO result = EmployeResponseDTO.from(employeservice.createEmploye(dto.toEmploye()));
		logger.info("Employé créé avec succès - ID: {}", result.id());
		return result;
	}

	@PutMapping("/api/employe/{id}")
	@PreAuthorize("hasRole('MAJ')")
	public EmployeResponseDTO updateEmploye(@PathVariable final Long id, @Valid @RequestBody EmployeRequestDTO dto) {
		logger.debug("Mise à jour employé ID: {} - prénom: {}, nom: {}", id, dto.prenom(), dto.nom());
		logger.info("Données employé validées, mise à jour en cours...");
		EmployeResponseDTO result = EmployeResponseDTO.from(employeservice.updateEmploye(id, dto.toEmploye()));
		logger.info("Employé mis à jour avec succès - ID: {}", result.id());
		return result;
	}

}
