package fr.leuwen.rhdemoAPI.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.web.SecurityFilterChain;

/**
 * Configuration de sécurité pour les tests d'intégration.
 * Cette configuration remplace SecurityConfig et désactive OAuth2/Keycloak.
 * Utilise @WithMockUser pour simuler l'authentification.
 * 
 * Activée uniquement pour le profil "test".
 */
@Configuration
@EnableWebSecurity
@EnableMethodSecurity
@Profile("test") // Active uniquement pour le profil "test"
public class TestSecurityConfig {

    @Bean
    public SecurityFilterChain testFilterChain(HttpSecurity http) throws Exception {
        http
            .csrf(csrf -> csrf.disable()) // Désactive CSRF pour simplifier les tests
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/who", "/error*", "/api-docs", "/actuator/**").permitAll()
                .anyRequest().authenticated()
            )
            // Utilise l'authentification basique pour les tests (mockée via @WithMockUser)
            .httpBasic(basic -> {});
        
        return http.build();
    }
}
