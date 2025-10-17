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
	info.append("Documentation Swagger UI sur /api-docs/swagger-ui/index.html <br>");
	info.append("Documentation OpenAPI sur /api-docs/docs <br>");
	info.append("Monitoring sur /actuator <br>");
	info.append("Info utilisateurs sur /who <br>");
	info.append("Logout sur /logout");
	return info.toString();
    }
 
}
