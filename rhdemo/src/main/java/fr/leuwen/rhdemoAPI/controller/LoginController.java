package fr.leuwen.rhdemoAPI.controller;

import java.security.Principal;
import java.util.Map;

import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.oauth2.client.OAuth2AuthorizedClient;
import org.springframework.security.oauth2.client.OAuth2AuthorizedClientService;
import org.springframework.security.oauth2.client.authentication.OAuth2AuthenticationToken;
import org.springframework.security.oauth2.core.oidc.OidcIdToken;
import org.springframework.security.oauth2.core.oidc.user.OidcUser;
import org.springframework.security.oauth2.core.user.DefaultOAuth2User;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class LoginController {

    private final OAuth2AuthorizedClientService authorizedClientService;

    public LoginController(OAuth2AuthorizedClientService authorizedClientService) {

	this.authorizedClientService = authorizedClientService;

    }

    // Pour traitement après authentification Oauth2 sur serveur identité
    // Selon la méthode (Login local ou OAuth2 ou ) on a des token de types
    // différents
    // avec une méthode d'extraction d'info dédiée
    @GetMapping("/")
    public String getUserInfo(Principal user, @AuthenticationPrincipal OidcUser oidcuser) {
	StringBuffer userInfo = new StringBuffer();
	if (user instanceof UsernamePasswordAuthenticationToken) {
	    userInfo.append(getUsernamePasswordLoginInfo(user));
	} else if (user instanceof OAuth2AuthenticationToken) {
	    userInfo.append(getOauth2LoginInfo(user, oidcuser));
	}
	return userInfo.toString();
    }

    // Extraction avec login local
    private StringBuffer getUsernamePasswordLoginInfo(Principal user) {
	StringBuffer usernameInfo = new StringBuffer();
	UsernamePasswordAuthenticationToken token = ((UsernamePasswordAuthenticationToken) user);
	if (token.isAuthenticated()) {
	    User u = (User) token.getPrincipal();
	    usernameInfo.append("Bienvenue, " + u.getUsername());
	} else {
	    usernameInfo.append("Problème d'authentification");
	}
	return usernameInfo;
    }

    // Extraction avec Oauth2
    private StringBuffer getOauth2LoginInfo(Principal user, OidcUser oidcuser){

		   StringBuffer protectedInfo = new StringBuffer();	
		   OAuth2AuthenticationToken authToken = ((OAuth2AuthenticationToken) user);
		   OAuth2AuthorizedClient authClient = this.authorizedClientService.loadAuthorizedClient(authToken.getAuthorizedClientRegistrationId(), authToken.getName());
		   if(authToken.isAuthenticated()){
	   
			   Map<String,Object> userAttributes = ((DefaultOAuth2User) authToken.getPrincipal()).getAttributes();   
			   String userToken = authClient.getAccessToken().getTokenValue();
			   protectedInfo.append("Bienvenue, " + userAttributes.get("name")+"<br><br>");
			   //Nécessite une demande spécifique en OAuth (claim) pas en OIDC
			   protectedInfo.append("Mail (Oauth)" + userAttributes.get("email")+"<br><br>");
			   }
			   else{
			   protectedInfo.append("Problème d'authentification");
			   }		   
		   if(oidcuser != null) {
			   OidcIdToken idToken = oidcuser.getIdToken();
			   if(idToken != null) {
			   protectedInfo.append("Valeurs portées par le token OIDC"+"<br><br>");
			   Map<String, Object> claims = idToken.getClaims();
	 		   	for (String key : claims.keySet()) {
				   protectedInfo.append("  " + key + ": " + claims.get(key)+"<br>");
			   	} 
			   } 
		   
		} else {
			   protectedInfo.append("Pas d'info OIDC");
		}	
		return protectedInfo;
    }
}
