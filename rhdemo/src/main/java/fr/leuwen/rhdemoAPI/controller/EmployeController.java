package fr.leuwen.rhdemoAPI.controller;

import java.util.Optional;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

import fr.leuwen.rhdemoAPI.model.Employe;
import fr.leuwen.rhdemoAPI.service.EmployeService;

@RestController
public class EmployeController {
    
    
	@Autowired
	private EmployeService employeservice;
	
	
	@GetMapping("/api/employes")	
	public Iterable<Employe> getEmployes() {
		return employeservice.getEmployes();
	}
	
	
	@GetMapping("/api/employe")	
	public Optional<Employe> getEmploye(final Long id) {
		return employeservice.getEmploye(id);
	}
	
	@DeleteMapping("/api/employe")
	public void deleteEmploye(final Long id) {
	      employeservice.deleteEmploye(id);
	     
	}
	
	@PostMapping ("/api/employe")
	public Employe saveEmploye(Employe employe) {
	      return employeservice.saveEmploye(employe);
	}	

}
