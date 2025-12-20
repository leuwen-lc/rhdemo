package fr.leuwen.rhdemoAPI.springconfig;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * Configuration Spring MVC pour gérer les ressources statiques
 *
 * CONTEXTE:
 * - En local: Spring Boot sert l'application à http://localhost:9000/
 * - En ephemere: nginx route /front/ vers le container rhdemo-app
 *
 * PROBLÈME:
 * - Vue.js avec publicPath: '/' génère des chemins absolus /js/app.js, /css/app.css
 * - Spring Boot cherche ces ressources dans /static/js/ et /static/css/ (OK en local)
 * - En ephemere, nginx reçoit /js/app.js mais doit le rediriger vers /front/js/app.js
 *
 * SOLUTION:
 * - Mapper /js/** vers classpath:/static/js/
 * - Mapper /css/** vers classpath:/static/css/
 * - Mapper /img/** vers classpath:/static/img/
 * - Mapper /fonts/** vers classpath:/static/fonts/
 *
 * Cela permet à Spring Boot de servir correctement les ressources même si nginx
 * route /front/js/app.js vers Spring Boot qui reçoit /js/app.js
 */
@Configuration
public class WebMvcConfig implements WebMvcConfigurer {

    @Override
    public void addResourceHandlers(@org.springframework.lang.NonNull ResourceHandlerRegistry registry) {
        // Mapper les ressources JavaScript
        registry.addResourceHandler("/js/**")
                .addResourceLocations("classpath:/static/js/");

        // Mapper les ressources CSS
        registry.addResourceHandler("/css/**")
                .addResourceLocations("classpath:/static/css/");

        // Mapper les images
        registry.addResourceHandler("/img/**")
                .addResourceLocations("classpath:/static/img/");

        // Mapper les polices de caractères
        registry.addResourceHandler("/fonts/**")
                .addResourceLocations("classpath:/static/fonts/");

        // Mapper favicon et fichiers SVG à la racine
        registry.addResourceHandler("/favicon.ico", "/favicon.svg")
                .addResourceLocations("classpath:/static/");
    }
}
