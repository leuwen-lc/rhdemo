package fr.leuwen.rhdemoAPI.config;

import fr.leuwen.rhdemoAPI.springconfig.CspPolicyBuilder;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.csrf.CsrfToken;
import org.springframework.security.web.csrf.CsrfTokenRequestAttributeHandler;
import org.springframework.security.web.csrf.CsrfTokenRequestHandler;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Bean;

import java.util.function.Supplier;

/**
 * Configuration de sécurité pour les tests d'intégration.
 * Remplace SecurityConfig (désactivé via @Profile("!test")) et désactive OAuth2/Keycloak.
 * Réutilise CspPolicyBuilder pour garantir que la CSP testée est strictement celle de production.
 * L'authentification est simulée via @WithMockUser.
 */
@Configuration
@EnableWebSecurity
@EnableMethodSecurity
@Profile("test")
public class TestSecurityConfig {

    @Autowired
    private CspPolicyBuilder cspPolicyBuilder;

    @Bean
    public SecurityFilterChain testFilterChain(HttpSecurity http) throws Exception {
        http
            .csrf(csrf -> csrf
                .csrfTokenRepository(cspPolicyBuilder.createCsrfTokenRepository())
                .csrfTokenRequestHandler(new TestSpaCsrfTokenRequestHandler())
                .ignoringRequestMatchers("/error*", "/api-docs", "/actuator/**")
            )
            .headers(headers -> headers
                .frameOptions(frame -> frame.disable())
                .contentSecurityPolicy(csp -> csp
                    .policyDirectives(cspPolicyBuilder.buildCspDirectives())
                )
            )
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/error*", "/logout").permitAll()
                .requestMatchers("/actuator/health", "/actuator/health/**").permitAll()
                .requestMatchers("/actuator/prometheus").permitAll()
                .requestMatchers("/actuator/**").hasRole("admin")
                .requestMatchers("/api-docs/**").hasRole("admin")
                .requestMatchers("/front").hasAnyRole("consult", "MAJ")
                .anyRequest().authenticated()
            )
            .httpBasic(basic -> {});

        return http.build();
    }
}

/**
 * Gestionnaire de requêtes CSRF pour les tests (copie du SpaCsrfTokenRequestHandler de SecurityConfig).
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
