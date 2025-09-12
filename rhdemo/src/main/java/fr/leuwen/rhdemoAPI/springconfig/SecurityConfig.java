package fr.leuwen.rhdemoAPI.springconfig;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.web.SecurityFilterChain;

@Configuration
@EnableWebSecurity
public class SecurityConfig {
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
	// désactive les controles Spring Security pour la console H2 et Tomcat
	http.authorizeHttpRequests(authorize -> authorize
		//H2 à désactiver en prod
		.requestMatchers("/h2-console/**").permitAll()
	        .requestMatchers(HttpMethod.POST,"/api/**").hasRole("MAJ")
	        .requestMatchers(HttpMethod.DELETE,"/api/**").hasRole("MAJ")
	        .requestMatchers(HttpMethod.PUT,"/api/**").hasRole("MAJ")
	        .requestMatchers(HttpMethod.GET,"/api/**").hasAnyRole("Consult","MAJ")
	        .anyRequest().authenticated()
	)
	.csrf(csrf -> csrf.disable()) // Désactive CSRF (!global!)
	.headers(headers -> headers.frameOptions(frameOptions -> frameOptions.disable())) 
	.formLogin(Customizer.withDefaults()).oauth2Login(Customizer.withDefaults());
	return http.build();
    }
}
