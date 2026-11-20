package fr.leuwen.rhdemoAPI.springconfig;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.web.csrf.CsrfToken;
import org.springframework.security.web.csrf.DefaultCsrfToken;

import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Tests unitaires pour SpaCsrfTokenRequestHandler (gestionnaire CSRF pour SPA, défini dans SecurityConfig).
 */
@DisplayName("SpaCsrfTokenRequestHandler - gestion du token CSRF pour la SPA")
class SpaCsrfTokenRequestHandlerTest {

    private static final String TOKEN_VALUE = "token-abc";
    private final CsrfToken token = new DefaultCsrfToken("X-XSRF-TOKEN", "_csrf", TOKEN_VALUE);
    private final SpaCsrfTokenRequestHandler handler = new SpaCsrfTokenRequestHandler();

    @Test
    @DisplayName("handle doit forcer la génération du token et l'exposer comme attribut de requête")
    void handle_ShouldForceTokenGenerationAndExposeAttribute() {
        MockHttpServletRequest request = new MockHttpServletRequest();
        AtomicInteger calls = new AtomicInteger();

        handler.handle(request, new MockHttpServletResponse(), () -> {
            calls.incrementAndGet();
            return token;
        });

        assertThat(calls.get()).isPositive();
        assertThat(((CsrfToken) request.getAttribute(CsrfToken.class.getName())).getToken()).isEqualTo(TOKEN_VALUE);
        assertThat(((CsrfToken) request.getAttribute("_csrf")).getToken()).isEqualTo(TOKEN_VALUE);
    }

    @Test
    @DisplayName("resolveCsrfTokenValue doit lire le token depuis l'en-tête")
    void resolveCsrfTokenValue_FromHeader() {
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.addHeader("X-XSRF-TOKEN", TOKEN_VALUE);

        assertThat(handler.resolveCsrfTokenValue(request, token)).isEqualTo(TOKEN_VALUE);
    }

    @Test
    @DisplayName("resolveCsrfTokenValue doit lire le token depuis le paramètre à défaut d'en-tête")
    void resolveCsrfTokenValue_FromParameter() {
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.setParameter("_csrf", TOKEN_VALUE);

        assertThat(handler.resolveCsrfTokenValue(request, token)).isEqualTo(TOKEN_VALUE);
    }

    @Test
    @DisplayName("resolveCsrfTokenValue doit retourner null si aucun token n'est fourni")
    void resolveCsrfTokenValue_NoToken() {
        assertThat(handler.resolveCsrfTokenValue(new MockHttpServletRequest(), token)).isNull();
    }
}
