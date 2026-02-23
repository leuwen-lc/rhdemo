package fr.leuwen.rhdemoAPI.controller;

import java.util.List;
import java.util.Map;

import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class AccueilController {

	@GetMapping("/api/userinfo")
	public Map<String, Object> getUserInfo(Authentication auth) {
		String username = auth.getName();
		List<String> roles = auth.getAuthorities().stream()
				.map(GrantedAuthority::getAuthority)
				.toList();
		return Map.of("username", username, "roles", roles);
	}

	@GetMapping("/")
	public String getInfo() {
		StringBuffer info = new StringBuffer();
		info.append("Avec role profil maj ou consult: <br>");
		info.append("API disponibles sur /api/... <br>");
		info.append("Front end disponible sur /front <br>");

		info.append("<br>Avec role profil admin: <br>");
		info.append("Monitoring sur /actuator (dispo en dev local uniquement)<br>");

		info.append(
				"<br>Documentation Swagger UI sur /api-docs/swagger-ui/index.html (dispo en dev local uniquement)<br>");
		info.append("Documentation OpenAPI sur /api-docs/docs (dispo en dev local uniquement)<br>");
		info.append("<br>Logout sur /logout");
		return info.toString();
	}

}
