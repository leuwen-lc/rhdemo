package fr.leuwen.rhdemoAPI.config;

import fr.leuwen.rhdemoAPI.model.Employe;
import fr.leuwen.rhdemoAPI.repository.EmployeRepository;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Profile;

/**
 * Configuration pour charger les données de test dans la base H2.
 * Activée uniquement pour le profil "test".
 */
@TestConfiguration
@Profile("test")
public class TestDataLoader {

    /**
     * Bean qui charge les données de test dans la base H2 après l'initialisation du contexte.
     * Cette approche garantit que Hibernate a déjà créé les tables via ddl-auto: create-drop.
     */
    @Bean
    public TestDataInitializer testDataInitializer(EmployeRepository employeRepository) {
        return new TestDataInitializer(employeRepository);
    }

    /**
     * Classe interne qui charge les données au démarrage du contexte Spring.
     */
    public static class TestDataInitializer {

        public TestDataInitializer(EmployeRepository employeRepository) {
            // Nettoyer toutes les données existantes
            employeRepository.deleteAll();

            // Créer les 4 employés de test
            Employe emp1 = new Employe();
            emp1.setPrenom("Laurent");
            emp1.setNom("Martin");
            emp1.setMail("laurent.martin@example.com");
            emp1.setAdresse("1 Rue de la Paix, Paris");
            employeRepository.save(emp1);

            Employe emp2 = new Employe();
            emp2.setPrenom("Sophie");
            emp2.setNom("Dubois");
            emp2.setMail("sophie.dubois@example.com");
            emp2.setAdresse("2 Avenue des Champs, Lyon");
            employeRepository.save(emp2);

            Employe emp3 = new Employe();
            emp3.setPrenom("Pierre");
            emp3.setNom("Bernard");
            emp3.setMail("pierre.bernard@example.com");
            emp3.setAdresse("3 Boulevard Victor Hugo, Marseille");
            employeRepository.save(emp3);

            Employe emp4 = new Employe();
            emp4.setPrenom("Marie");
            emp4.setNom("Durand");
            emp4.setMail("marie.durand@example.com");
            emp4.setAdresse("4 Place de la République, Toulouse");
            employeRepository.save(emp4);
        }
    }
}
