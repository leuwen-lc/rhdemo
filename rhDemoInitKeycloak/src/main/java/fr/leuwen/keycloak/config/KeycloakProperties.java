package fr.leuwen.keycloak.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.ArrayList;
import java.util.List;

/**
 * Configuration properties pour l'initialisation de Keycloak.
 * Remplace l'ancien ConfigLoader.java avec un binding automatique du fichier YAML.
 */
@ConfigurationProperties(prefix = "keycloak")
public class KeycloakProperties {

    private String serverUrl;
    private Admin admin = new Admin();
    private Realm realm = new Realm();
    private Client client = new Client();
    private List<User> users = new ArrayList<>();

    // Getters et Setters
    public String getServerUrl() {
        return serverUrl;
    }

    public void setServerUrl(String serverUrl) {
        this.serverUrl = serverUrl;
    }

    public Admin getAdmin() {
        return admin;
    }

    public void setAdmin(Admin admin) {
        this.admin = admin;
    }

    public Realm getRealm() {
        return realm;
    }

    public void setRealm(Realm realm) {
        this.realm = realm;
    }

    public Client getClient() {
        return client;
    }

    public void setClient(Client client) {
        this.client = client;
    }

    public List<User> getUsers() {
        return users;
    }

    public void setUsers(List<User> users) {
        this.users = users;
    }

    // Classes internes pour la structure de configuration
    public static class Admin {
        private String username;
        private String password;
        private String realm = "master";

        public String getUsername() {
            return username;
        }

        public void setUsername(String username) {
            this.username = username;
        }

        public String getPassword() {
            return password;
        }

        public void setPassword(String password) {
            this.password = password;
        }

        public String getRealm() {
            return realm;
        }

        public void setRealm(String realm) {
            this.realm = realm;
        }
    }

    public static class Realm {
        private String name;
        private String displayName;
        private boolean enabled = true;
        private boolean registrationAllowed = false;
        private boolean registrationEmailAsUsername = false;
        private boolean resetPasswordAllowed = true;
        private boolean editUsernameAllowed = false;
        private boolean loginWithEmailAllowed = true;
        private boolean duplicateEmailsAllowed = false;
        private boolean rememberMe = true;
        private int ssoSessionIdleTimeout = 1800; // 30 minutes
        private int ssoSessionMaxLifespan = 36000; // 10 heures
        private int accessTokenLifespan = 300; // 5 minutes

        public String getName() {
            return name;
        }

        public void setName(String name) {
            this.name = name;
        }

        public String getDisplayName() {
            return displayName;
        }

        public void setDisplayName(String displayName) {
            this.displayName = displayName;
        }

        public boolean isEnabled() {
            return enabled;
        }

        public void setEnabled(boolean enabled) {
            this.enabled = enabled;
        }

        public boolean isRegistrationAllowed() {
            return registrationAllowed;
        }

        public void setRegistrationAllowed(boolean registrationAllowed) {
            this.registrationAllowed = registrationAllowed;
        }

        public boolean isRegistrationEmailAsUsername() {
            return registrationEmailAsUsername;
        }

        public void setRegistrationEmailAsUsername(boolean registrationEmailAsUsername) {
            this.registrationEmailAsUsername = registrationEmailAsUsername;
        }

        public boolean isResetPasswordAllowed() {
            return resetPasswordAllowed;
        }

        public void setResetPasswordAllowed(boolean resetPasswordAllowed) {
            this.resetPasswordAllowed = resetPasswordAllowed;
        }

        public boolean isEditUsernameAllowed() {
            return editUsernameAllowed;
        }

        public void setEditUsernameAllowed(boolean editUsernameAllowed) {
            this.editUsernameAllowed = editUsernameAllowed;
        }

        public boolean isLoginWithEmailAllowed() {
            return loginWithEmailAllowed;
        }

        public void setLoginWithEmailAllowed(boolean loginWithEmailAllowed) {
            this.loginWithEmailAllowed = loginWithEmailAllowed;
        }

        public boolean isDuplicateEmailsAllowed() {
            return duplicateEmailsAllowed;
        }

        public void setDuplicateEmailsAllowed(boolean duplicateEmailsAllowed) {
            this.duplicateEmailsAllowed = duplicateEmailsAllowed;
        }

        public boolean isRememberMe() {
            return rememberMe;
        }

        public void setRememberMe(boolean rememberMe) {
            this.rememberMe = rememberMe;
        }

        public int getSsoSessionIdleTimeout() {
            return ssoSessionIdleTimeout;
        }

        public void setSsoSessionIdleTimeout(int ssoSessionIdleTimeout) {
            this.ssoSessionIdleTimeout = ssoSessionIdleTimeout;
        }

        public int getSsoSessionMaxLifespan() {
            return ssoSessionMaxLifespan;
        }

        public void setSsoSessionMaxLifespan(int ssoSessionMaxLifespan) {
            this.ssoSessionMaxLifespan = ssoSessionMaxLifespan;
        }

        public int getAccessTokenLifespan() {
            return accessTokenLifespan;
        }

        public void setAccessTokenLifespan(int accessTokenLifespan) {
            this.accessTokenLifespan = accessTokenLifespan;
        }
    }

    public static class Client {
        private String clientId;
        private String name;
        private String secret;
        private String rootUrl = "http://localhost:9000/";
        private String baseUrl = "";
        private String adminUrl = "";
        private List<String> redirectUris = new ArrayList<>();
        private List<String> webOrigins = new ArrayList<>();
        private List<String> roles = new ArrayList<>();

        public String getClientId() {
            return clientId;
        }

        public void setClientId(String clientId) {
            this.clientId = clientId;
        }

        public String getName() {
            return name;
        }

        public void setName(String name) {
            this.name = name;
        }

        public String getSecret() {
            return secret;
        }

        public void setSecret(String secret) {
            this.secret = secret;
        }

        public String getRootUrl() {
            return rootUrl;
        }

        public void setRootUrl(String rootUrl) {
            this.rootUrl = rootUrl;
        }

        public String getBaseUrl() {
            return baseUrl;
        }

        public void setBaseUrl(String baseUrl) {
            this.baseUrl = baseUrl;
        }

        public String getAdminUrl() {
            return adminUrl;
        }

        public void setAdminUrl(String adminUrl) {
            this.adminUrl = adminUrl;
        }

        public List<String> getRedirectUris() {
            return redirectUris;
        }

        public void setRedirectUris(List<String> redirectUris) {
            this.redirectUris = redirectUris;
        }

        public List<String> getWebOrigins() {
            return webOrigins;
        }

        public void setWebOrigins(List<String> webOrigins) {
            this.webOrigins = webOrigins;
        }

        public List<String> getRoles() {
            return roles;
        }

        public void setRoles(List<String> roles) {
            this.roles = roles;
        }
    }

    public static class User {
        private String username;
        private String password;
        private String email;
        private String firstName;
        private String lastName;
        private List<String> roles = new ArrayList<>();

        public String getUsername() {
            return username;
        }

        public void setUsername(String username) {
            this.username = username;
        }

        public String getPassword() {
            return password;
        }

        public void setPassword(String password) {
            this.password = password;
        }

        public String getEmail() {
            return email;
        }

        public void setEmail(String email) {
            this.email = email;
        }

        public String getFirstName() {
            return firstName;
        }

        public void setFirstName(String firstName) {
            this.firstName = firstName;
        }

        public String getLastName() {
            return lastName;
        }

        public void setLastName(String lastName) {
            this.lastName = lastName;
        }

        public List<String> getRoles() {
            return roles;
        }

        public void setRoles(List<String> roles) {
            this.roles = roles;
        }
    }
}
