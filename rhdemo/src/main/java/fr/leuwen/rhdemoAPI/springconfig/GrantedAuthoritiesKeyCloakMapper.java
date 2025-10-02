package fr.leuwen.rhdemoAPI.springconfig;

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.authority.mapping.GrantedAuthoritiesMapper;
import org.springframework.security.oauth2.core.oidc.user.OidcUserAuthority;
import org.springframework.security.oauth2.core.user.OAuth2UserAuthority;
import org.springframework.stereotype.Component;

@Component
public class GrantedAuthoritiesKeyCloakMapper implements GrantedAuthoritiesMapper {

    @Value("${spring.security.oauth2.client.registration.keycloak.client-id}")
    private String rhDemoClientID;

    @Override
    public Collection<? extends GrantedAuthority> mapAuthorities(Collection<? extends GrantedAuthority> authorities) {
        Set<GrantedAuthority> mappedAuthorities = new HashSet<>();

        authorities.forEach(authority -> {
           //authority.idtoken.claims(..).key="resource_access"/Value RHDemo={roles=[ROLE_admin]}
            if (OidcUserAuthority.class.isInstance(authority)) {
                final OidcUserAuthority oidcUserAuthority = (OidcUserAuthority) authority;
                mappedAuthorities.addAll(extractAuthorities(oidcUserAuthority.getIdToken().getClaims()));

            } else if (OAuth2UserAuthority.class.isInstance(authority)) {
                    final OAuth2UserAuthority oauth2UserAuthority = (OAuth2UserAuthority) authority;
                    final Map userAttributes = oauth2UserAuthority.getAttributes();
                    mappedAuthorities.addAll(extractAuthorities(userAttributes));
            }
        });

        return mappedAuthorities;
    }
    private Collection<GrantedAuthority> extractAuthorities(Map<String, Object> claims) {
	//On va chercher l'information sur le role dans l'arbre de données de toutes les claims
	Collection<GrantedAuthority> grantedAuths = new ArrayList<GrantedAuthority>();
	Map<String,Object> ressourceAccess=(Map<String,Object>)claims.get("resource_access");
	Map<String,Object> clientID=(Map<String,Object>)ressourceAccess.get(rhDemoClientID);
	List<String> roles=(List<String>)clientID.get("roles");
        if (roles!=null) {	
	grantedAuths=roles.stream().filter(e->e.startsWith("ROLE_"))
		      .map(SimpleGrantedAuthority::new)
		      .collect(Collectors.toList());      
	}
    return grantedAuths;
    }
}

    
