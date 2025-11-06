package fr.leuwen.rhdemoAPI.controller;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;

/*Sert pour rediriger les requêtes vers l'application frontend (bootstrapée par index.html) quand l'utilisateur presse sur CTRL+F5
 *En effet sans celà une erreur 404 surviendrait car le frontend n'est pas encore chargé et ne peut intercepté
 */
@Controller
public class FrontendController {

    // Capture toutes les routes commençant par /front (et ses sous-routes)
    @GetMapping({"/front", "/front/**"})
    public String forwardToIndex() {
        return "forward:/index.html";
    }
}
