package fr.leuwen.rhdemoAPI.springconfig;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.oauth2.client.oidc.web.logout.OidcClientInitiatedLogoutSuccessHandler;
import org.springframework.security.oauth2.client.registration.ClientRegistrationRepository;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.logout.LogoutSuccessHandler;

@Configuration
@EnableWebSecurity
//Permet de positionner des annotations de type @PreAuthorize("hasRole('rolexx')")
@EnableMethodSecurity
public class SecurityConfig {
    @Autowired
    private GrantedAuthoritiesKeyCloakMapper keycloakmapper;
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http, LogoutSuccessHandler logoutSuccessHandler) throws Exception {
	http 
	.csrf(csrf -> csrf.disable()) // Désactive CSRF (!global!)
	.authorizeHttpRequests(auth -> auth 
            .requestMatchers("/who","/error*","/logout").permitAll()
            .requestMatchers("/actuator/**").hasRole("admin")
            // Pour les requètes REST les filtres de roles sont directement au niveau des méthodes du controleur
            .anyRequest().authenticated())
	.oauth2Login(oauth2 -> oauth2
		    .userInfoEndpoint(userInfo -> userInfo
			        .userAuthoritiesMapper(this.keycloakmapper)))
	.logout(logout -> logout 
		.logoutUrl("/logout")
	        .logoutSuccessHandler(logoutSuccessHandler))
        ;
	//	.formLogin(Customizer.withDefaults())
	//.headers(headers -> headers.frameOptions(frameOptions -> frameOptions.disable())) 
	return http.build();
    }
    
    //Logout handler spécifique appelé par Spring.
    @Bean
    public LogoutSuccessHandler oidcLogoutSuccessHandler(ClientRegistrationRepository clientRegistrationRepository) {
        OidcClientInitiatedLogoutSuccessHandler successHandler =
            new OidcClientInitiatedLogoutSuccessHandler(clientRegistrationRepository);
        successHandler.setPostLogoutRedirectUri("{baseUrl}/"); // optionnel, page de retour
        return successHandler;
    }
}
