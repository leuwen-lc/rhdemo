package fr.leuwen.rhdemoAPI.exception;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * Réponse d'erreur standardisée de l'API.
 * Les setters de l'ancienne classe POJO ne sont pas nécessaires :
 * GlobalExceptionHandler utilise uniquement les constructeurs.
 */
public record ErrorResponse(
    int status,
    String message,
    LocalDateTime timestamp,
    Map<String, String> errors
) {
    public ErrorResponse(int status, String message, LocalDateTime timestamp) {
        this(status, message, timestamp, null);
    }
}
