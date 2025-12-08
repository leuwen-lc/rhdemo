package fr.leuwen.rhdemoAPI.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.csrf.CookieCsrfTokenRepository;
import org.springframework.security.web.csrf.CsrfToken;
import org.springframework.security.web.csrf.CsrfTokenRequestAttributeHandler;
import org.springframework.security.web.csrf.CsrfTokenRequestHandler;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.util.function.Supplier;

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
            // Active la protection CSRF avec cookie (comme en production)
            .csrf(csrf -> csrf
                .csrfTokenRepository(CookieCsrfTokenRepository.withHttpOnlyFalse())
                .csrfTokenRequestHandler(new TestSpaCsrfTokenRequestHandler())
                .ignoringRequestMatchers("/who", "/error*", "/api-docs", "/actuator/**")
            )
            // Configure les headers de sécurité (comme en production)
            .headers(headers -> headers
                .frameOptions(frame -> frame.disable())
                .contentSecurityPolicy(csp -> csp
                    .policyDirectives(buildCspDirectives())
                )
            )
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/who", "/error*", "/logout", "/api-docs").permitAll()
                .requestMatchers("/front").hasAnyRole("consult", "MAJ")
                .requestMatchers("/actuator/**").hasRole("admin")
                .anyRequest().authenticated()
            )
            // Utilise l'authentification basique pour les tests (mockée via @WithMockUser)
            .httpBasic(basic -> {});

        return http.build();
    }

    /**
     * Construit les directives Content-Security-Policy (CSP) pour les tests.
     * Version simplifiée sans URL Keycloak dynamique.
     */
    private String buildCspDirectives() {
        StringBuilder csp = new StringBuilder();
        csp.append("default-src 'self'; ");
        csp.append("script-src 'self'; ");
        csp.append("style-src 'self'; ");
        csp.append("img-src 'self' data: https:; ");
        csp.append("font-src 'self' data:; ");
        csp.append("connect-src 'self'; ");
        csp.append("frame-src 'self'; ");
        csp.append("frame-ancestors 'self'; ");
        csp.append("form-action 'self'; ");
        csp.append("object-src 'none'; ");
        csp.append("base-uri 'self'");
        return csp.toString();
    }
}

/**
 * Gestionnaire de requêtes CSRF pour les tests.
 * Copie du SpaCsrfTokenRequestHandler de SecurityConfig.
 */
final class TestSpaCsrfTokenRequestHandler implements CsrfTokenRequestHandler {
    private final CsrfTokenRequestAttributeHandler delegate = new CsrfTokenRequestAttributeHandler();

    @Override
    public void handle(HttpServletRequest request, HttpServletResponse response, Supplier<CsrfToken> csrfToken) {
        CsrfToken token = csrfToken.get();
        this.delegate.handle(request, response, () -> token);
    }

    @Override
    public String resolveCsrfTokenValue(HttpServletRequest request, CsrfToken csrfToken) {
        return this.delegate.resolveCsrfTokenValue(request, csrfToken);
    }
}
