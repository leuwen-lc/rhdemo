package fr.leuwen.rhdemoAPI.repository;

import org.springframework.data.repository.CrudRepository;
import fr.leuwen.rhdemoAPI.model.Employe;

public interface EmployeRepository extends CrudRepository<Employe,Long> {
	

}
