package fr.leuwen.rhdemoAPI.service;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;

import fr.leuwen.rhdemoAPI.exception.EmployeNotFoundException;
import fr.leuwen.rhdemoAPI.model.Employe;
import fr.leuwen.rhdemoAPI.repository.EmployeRepository;

@Service
public class EmployeService {
	private final EmployeRepository employerepository;

	// Autowired par défaut avec Spring Boot
	public EmployeService(EmployeRepository employerepository) {
		this.employerepository = employerepository;
	}
	
	public Employe getEmploye(final Long id) {
        return employerepository.findById(id)
            .orElseThrow(() -> new EmployeNotFoundException(id));
    }


    public Iterable<Employe> getEmployes() {
        return employerepository.findAll();
    }

    public Page<Employe> getEmployesPage(Pageable pageable) {
        return employerepository.findAll(pageable);
    }

    public Page<Employe> getEmployesPage(Specification<Employe> spec, Pageable pageable) {
        return employerepository.findAll(spec, pageable);
    }

    public void deleteEmploye(final Long id) {
        // Vérifier que l'employé existe avant de le supprimer
        if (!employerepository.existsById(id)) {
            throw new EmployeNotFoundException(id);
        }
        employerepository.deleteById(id);
    }

    public Employe saveEmploye(Employe employe) {
        Employe savedEmploye = employerepository.save(employe);
        return savedEmploye;
    }
}
