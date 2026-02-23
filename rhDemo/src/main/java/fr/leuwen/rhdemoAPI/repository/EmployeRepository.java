package fr.leuwen.rhdemoAPI.repository;

import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.repository.CrudRepository;
import org.springframework.data.repository.PagingAndSortingRepository;
import fr.leuwen.rhdemoAPI.model.Employe;

public interface EmployeRepository extends CrudRepository<Employe,Long>, PagingAndSortingRepository<Employe,Long>, JpaSpecificationExecutor<Employe> {
	

}
