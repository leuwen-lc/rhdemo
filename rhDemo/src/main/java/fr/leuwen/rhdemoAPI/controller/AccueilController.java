package fr.leuwen.rhdemoAPI.controller;

import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class AccueilController {

    @GetMapping("/who")
    public String getUserInfo() {
	StringBuffer userInfo=new StringBuffer();
	Authentication auth = SecurityContextHolder.getContext().getAuthentication();
	userInfo.append("Principal <br>");
	userInfo.append(auth.getPrincipal()+"<br><br>");
	userInfo.append("Authorities <br>");
	userInfo.append(auth.getAuthorities());
	return userInfo.toString();
    }
    
    @GetMapping("/")
    public String getInfo() {
	StringBuffer info=new StringBuffer();
	info.append("API disponibles sur /api/... <br>");
	info.append("Front end disponible sur /front <br>");
	info.append("Documentation Swagger UI sur /api-docs/swagger-ui/index.html (dispo en dev local uniquement)<br>");
	info.append("Documentation OpenAPI sur /api-docs/docs (dispo en dev local uniquement)<br>");
	info.append("Monitoring sur /actuator (dispo en dev local uniquement)<br>");
	info.append("Info utilisateurs sur /who (dispo en dev local uniquement)<br>");
	info.append("Logout sur /logout");
	return info.toString();
    }
 
}
