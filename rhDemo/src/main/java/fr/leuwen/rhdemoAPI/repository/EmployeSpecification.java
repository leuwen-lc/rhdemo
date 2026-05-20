package fr.leuwen.rhdemoAPI.repository;

import java.util.ArrayList;
import java.util.List;

import org.springframework.data.jpa.domain.Specification;

import fr.leuwen.rhdemoAPI.model.Employe;
import jakarta.persistence.criteria.Predicate;

public final class EmployeSpecification {

	private EmployeSpecification() {
	}

	public static Specification<Employe> withFilters(String prenom, String nom, String mail, String adresse) {
		return (root, query, cb) -> {
			List<Predicate> predicates = new ArrayList<>();
			if (prenom != null && !prenom.isBlank()) {
				predicates.add(cb.like(cb.lower(root.get("prenom")), "%" + escapeLike(prenom.toLowerCase()) + "%", '\\'));
			}
			if (nom != null && !nom.isBlank()) {
				predicates.add(cb.like(cb.lower(root.get("nom")), "%" + escapeLike(nom.toLowerCase()) + "%", '\\'));
			}
			if (mail != null && !mail.isBlank()) {
				predicates.add(cb.like(cb.lower(root.get("mail")), "%" + escapeLike(mail.toLowerCase()) + "%", '\\'));
			}
			if (adresse != null && !adresse.isBlank()) {
				predicates.add(cb.like(cb.lower(root.get("adresse")), "%" + escapeLike(adresse.toLowerCase()) + "%", '\\'));
			}
			return cb.and(predicates.toArray(new Predicate[0]));
		};
	}

	private static String escapeLike(String value) {
		return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_");
	}
}
