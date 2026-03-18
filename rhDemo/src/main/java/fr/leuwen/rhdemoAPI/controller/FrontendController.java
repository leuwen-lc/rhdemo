package fr.leuwen.rhdemoAPI.controller;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.io.ClassPathResource;
import org.springframework.core.io.Resource;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.nio.charset.StandardCharsets;

/*
 * Sert l'index.html de l'application Vue.js pour toutes les routes /front/**
 * (navigation directe, CTRL+F5, deep link).
 *
 * Pourquoi ResponseEntity<Resource> et non "forward:/index.html" ?
 * Le dispatch FORWARD de Tomcat désenveloppe la réponse jusqu'au Response natif
 * Tomcat, en bypassant le HeaderWriterResponse wrapper de Spring Security.
 * Résultat : le HeaderWriterFilter ne peut pas écrire ses headers (CSP, Cache-Control…)
 * sur la réponse FORWARD. En retournant directement via ResponseEntity, on reste
 * dans le dispatch REQUEST original où le wrapper est actif et les headers sont écrits.
 */
@RestController
public class FrontendController {

    private static final Logger log = LoggerFactory.getLogger(FrontendController.class);
    private static final Resource INDEX_HTML = new ClassPathResource("static/index.html");

    @GetMapping({"/front", "/front/**"})
    public ResponseEntity<Resource> serveIndex(HttpServletRequest request, HttpServletResponse response) {
        log.debug("FrontendController.serveIndex chemin={} query={}", request.getRequestURI(), request.getQueryString());
        log.debug("Type du wrapper de réponse : {}", response.getClass().getName());
        log.debug("Header CSP à l'entrée du contrôleur : {}", response.getHeader("Content-Security-Policy"));
        return ResponseEntity.ok()
                .contentType(new MediaType(MediaType.TEXT_HTML, StandardCharsets.UTF_8))
                .body(INDEX_HTML);
    }
}
