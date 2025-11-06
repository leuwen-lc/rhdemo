package fr.leuwen.rhdemoAPI.service;

import java.util.Optional;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;

import fr.leuwen.rhdemoAPI.model.Employe;
import fr.leuwen.rhdemoAPI.repository.EmployeRepository;

@Service
public class EmployeService {
	@Autowired
	private EmployeRepository employerepository;
	
	public Optional<Employe> getEmploye(final Long id) {
        return employerepository.findById(id);
    }


    public Iterable<Employe> getEmployes() {
        return employerepository.findAll();
    }

    public Page<Employe> getEmployesPage(Pageable pageable) {
        return employerepository.findAll(pageable);
    }

    public void deleteEmploye(final Long id) {
        employerepository.deleteById(id);
    }

    public Employe saveEmploye(Employe employe) {

        Employe savedEmploye = employerepository.save(employe);

        return savedEmploye;
    }
}
