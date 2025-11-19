package fr.leuwen.rhdemoAPI.exception;

/**
 * Exception levée quand un employé est introuvable
 */
public class EmployeNotFoundException extends RuntimeException {
    
    public EmployeNotFoundException(Long id) {
        super("Employé introuvable avec l'ID: " + id);
    }
    
    public EmployeNotFoundException(String message) {
        super(message);
    }
}
