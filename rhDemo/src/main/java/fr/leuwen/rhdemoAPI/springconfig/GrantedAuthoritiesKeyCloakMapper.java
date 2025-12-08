package fr.leuwen.rhdemoAPI.springconfig;

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Profile;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.authority.mapping.GrantedAuthoritiesMapper;
import org.springframework.security.oauth2.core.oidc.user.OidcUserAuthority;
import org.springframework.security.oauth2.core.user.OAuth2UserAuthority;
import org.springframework.stereotype.Component;

@Component
@Profile("!test") // Désactive ce mapper pour les tests (Keycloak non disponible en test)
public class GrantedAuthoritiesKeyCloakMapper implements GrantedAuthoritiesMapper {

    private static final Logger log = LoggerFactory.getLogger(GrantedAuthoritiesKeyCloakMapper.class);

    @Value("${spring.security.oauth2.client.registration.keycloak.client-id}")
    private String rhDemoClientID;

    @Override
    public Collection<? extends GrantedAuthority> mapAuthorities(Collection<? extends GrantedAuthority> authorities) {
        Set<GrantedAuthority> mappedAuthorities = new HashSet<>();

        authorities.forEach(authority -> {
            if (OidcUserAuthority.class.isInstance(authority)) {
                final OidcUserAuthority oidcUserAuthority = (OidcUserAuthority) authority;
                mappedAuthorities.addAll(extractAuthorities(oidcUserAuthority.getIdToken().getClaims()));

            } else if (OAuth2UserAuthority.class.isInstance(authority)) {
                    final OAuth2UserAuthority oauth2UserAuthority = (OAuth2UserAuthority) authority;
                    final Map<String, Object> userAttributes = oauth2UserAuthority.getAttributes();
                    mappedAuthorities.addAll(extractAuthorities(userAttributes));
            }
        });

        return mappedAuthorities;
    }

    /**
     * Extrait les authorities depuis les claims du token JWT Keycloak
     * @param claims Les claims du token JWT
     * @return Collection des authorities extraites
     */
    @SuppressWarnings("unchecked") // Les casts sont nécessaires car les claims JWT sont typées Object
    private Collection<GrantedAuthority> extractAuthorities(Map<String, Object> claims) {
        log.debug("Extraction des authorities depuis les claims: {}", claims);
        // On va chercher l'information sur le role dans l'arbre de données de toutes les claims
        Collection<GrantedAuthority> grantedAuths = new ArrayList<>();

        // Cast nécessaire : resource_access est un Map mais claims.get() retourne Object
        Map<String, Object> ressourceAccess = (Map<String, Object>) claims.get("resource_access");
        if (ressourceAccess == null) {
            throw new IllegalStateException("Pas de claim 'resource_access' trouvée dans le ID token, probablement due à un configuration non faite dans Keycloak");
        }

        // Cast nécessaire : clientID est un Map mais ressourceAccess.get() retourne Object
        Map<String, Object> clientID = (Map<String, Object>) ressourceAccess.get(rhDemoClientID);

        // Vérifier que le client ID existe dans resource_access
        if (clientID == null) {
            log.warn("Client ID '{}' non trouvé dans resource_access. Clients disponibles: {}", rhDemoClientID, ressourceAccess.keySet());
            return grantedAuths; // Retourner liste vide au lieu de NPE
        }

        // Cast nécessaire : roles est une List mais clientID.get() retourne Object
        List<String> roles = (List<String>) clientID.get("roles");
        if (roles != null) {
            grantedAuths = roles.stream()
                .filter(e -> e.startsWith("ROLE_"))
                .map(SimpleGrantedAuthority::new)
                .collect(Collectors.toList());
        }
        return grantedAuths;
    }
}

    
