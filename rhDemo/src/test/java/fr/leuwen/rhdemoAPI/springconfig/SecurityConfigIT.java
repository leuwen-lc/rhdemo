package fr.leuwen.rhdemoAPI.springconfig;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.hamcrest.Matchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * Tests d'intégration pour SecurityConfig.
 *
 * Couverture:
 * - Content-Security-Policy (CSP) headers
 * - Contrôle d'accès basé sur les roles
 * - Configuration des headers de sécurité
 *
 * NOTE: Ces tests utilisent le profil "test" qui désactive SecurityConfig (@Profile("!test"))
 * et utilise TestSecurityConfig qui réplique la configuration de sécurité pour les tests.
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@DisplayName("SecurityConfig - Tests d'intégration")
class SecurityConfigIT {

    @Autowired
    private MockMvc mockMvc;

    // ==================== Tests du contrôle d'accès basé sur les roles ====================

    @Test
    @DisplayName("GET /actuator/health doit nécessiter le role ROLE_admin")
    @WithMockUser(roles = {"admin"})
    void testActuatorEndpoint_WithAdminRole_ShouldBeAccessible() throws Exception {
        mockMvc.perform(get("/actuator/health"))
            .andExpect(status().isOk());
    }

    @Test
    @DisplayName("GET /actuator/health doit refuser l'accès sans role admin")
    @WithMockUser(roles = {"consult"})
    void testActuatorEndpoint_WithoutAdminRole_ShouldBeForbidden() throws Exception {
        mockMvc.perform(get("/actuator/health"))
            .andExpect(status().isForbidden()); // 403 Forbidden
    }

    @Test
    @DisplayName("GET /actuator/health doit refuser l'accès sans authentification")
    void testActuatorEndpoint_WithoutAuthentication_ShouldBeUnauthorized() throws Exception {
        mockMvc.perform(get("/actuator/health"))
            .andExpect(status().isUnauthorized()); // 401 Unauthorized
    }

    // ==================== Tests des headers de sécurité ====================

    @Test
    @DisplayName("Doit inclure les headers Content-Security-Policy (CSP)")
    @WithMockUser(roles = {"admin"})
    void testCspHeader_ShouldBePresent() throws Exception {
        mockMvc.perform(get("/actuator/health"))
            .andExpect(header().exists("Content-Security-Policy"));
    }

    @Test
    @DisplayName("CSP doit contenir 'default-src self'")
    @WithMockUser(roles = {"admin"})
    void testCspHeader_ShouldContainDefaultSrcSelf() throws Exception {
        mockMvc.perform(get("/actuator/health"))
            .andExpect(header().string("Content-Security-Policy", containsString("default-src 'self'")));
    }

    @Test
    @DisplayName("CSP doit contenir 'script-src self' (sans unsafe-inline ni unsafe-eval)")
    @WithMockUser(roles = {"admin"})
    void testCspHeader_ShouldContainScriptSrcSelfOnly() throws Exception {
        mockMvc.perform(get("/actuator/health"))
            .andExpect(header().string("Content-Security-Policy", containsString("script-src 'self'")))
            .andExpect(header().string("Content-Security-Policy", not(containsString("unsafe-inline"))))
            .andExpect(header().string("Content-Security-Policy", not(containsString("unsafe-eval"))));
    }

    @Test
    @DisplayName("CSP doit contenir 'style-src self' (sans unsafe-inline)")
    @WithMockUser(roles = {"admin"})
    void testCspHeader_ShouldContainStyleSrcSelfOnly() throws Exception {
        mockMvc.perform(get("/actuator/health"))
            .andExpect(header().string("Content-Security-Policy", containsString("style-src 'self'")))
            .andExpect(header().string("Content-Security-Policy", not(containsString("unsafe-inline"))));
    }

    @Test
    @DisplayName("CSP doit contenir 'img-src self data: https:'")
    @WithMockUser(roles = {"admin"})
    void testCspHeader_ShouldContainImgSrc() throws Exception {
        mockMvc.perform(get("/actuator/health"))
            .andExpect(header().string("Content-Security-Policy", containsString("img-src 'self' data: https:")));
    }

    @Test
    @DisplayName("CSP doit contenir 'font-src self data:'")
    @WithMockUser(roles = {"admin"})
    void testCspHeader_ShouldContainFontSrc() throws Exception {
        mockMvc.perform(get("/actuator/health"))
            .andExpect(header().string("Content-Security-Policy", containsString("font-src 'self' data:")));
    }

    @Test
    @DisplayName("CSP doit contenir 'connect-src self'")
    @WithMockUser(roles = {"admin"})
    void testCspHeader_ShouldContainConnectSrc() throws Exception {
        mockMvc.perform(get("/actuator/health"))
            .andExpect(header().string("Content-Security-Policy", containsString("connect-src 'self'")));
    }

    @Test
    @DisplayName("CSP doit contenir 'frame-src self'")
    @WithMockUser(roles = {"admin"})
    void testCspHeader_ShouldContainFrameSrc() throws Exception {
        mockMvc.perform(get("/actuator/health"))
            .andExpect(header().string("Content-Security-Policy", containsString("frame-src 'self'")));
    }

    @Test
    @DisplayName("CSP doit contenir 'frame-ancestors self'")
    @WithMockUser(roles = {"admin"})
    void testCspHeader_ShouldContainFrameAncestors() throws Exception {
        mockMvc.perform(get("/actuator/health"))
            .andExpect(header().string("Content-Security-Policy", containsString("frame-ancestors 'self'")));
    }

    @Test
    @DisplayName("CSP doit contenir 'form-action self'")
    @WithMockUser(roles = {"admin"})
    void testCspHeader_ShouldContainFormAction() throws Exception {
        mockMvc.perform(get("/actuator/health"))
            .andExpect(header().string("Content-Security-Policy", containsString("form-action 'self'")));
    }

    @Test
    @DisplayName("CSP doit contenir 'object-src none'")
    @WithMockUser(roles = {"admin"})
    void testCspHeader_ShouldContainObjectSrcNone() throws Exception {
        mockMvc.perform(get("/actuator/health"))
            .andExpect(header().string("Content-Security-Policy", containsString("object-src 'none'")));
    }

    @Test
    @DisplayName("CSP doit contenir 'base-uri self'")
    @WithMockUser(roles = {"admin"})
    void testCspHeader_ShouldContainBaseUri() throws Exception {
        mockMvc.perform(get("/actuator/health"))
            .andExpect(header().string("Content-Security-Policy", containsString("base-uri 'self'")));
    }
}
