package ai.tuesday.client;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public final class UrlPolicyTest {
    @Test
    public void normalizesHttpsOrigin() {
        assertEquals("https://example.com", UrlPolicy.normalizeBackend(" https://example.com/ ", false));
    }

    @Test
    public void rejectsCredentialsAndPaths() {
        assertNull(UrlPolicy.normalizeBackend("https://user:pass@example.com", false));
        assertNull(UrlPolicy.normalizeBackend("https://example.com/path", false));
    }

    @Test
    public void onlyAllowsHttpForLocalDebug() {
        assertNull(UrlPolicy.normalizeBackend("http://example.com", true));
        assertNull(UrlPolicy.normalizeBackend("http://localhost:8000", false));
        assertEquals("http://localhost:8000", UrlPolicy.normalizeBackend("http://localhost:8000", true));
        assertEquals("http://10.0.2.2:8000", UrlPolicy.normalizeBackend("http://10.0.2.2:8000", true));
    }

    @Test
    public void comparesEffectiveOrigins() {
        assertTrue(UrlPolicy.sameOrigin("https://example.com/path", "https://example.com"));
        assertTrue(UrlPolicy.sameOrigin("https://example.com:443/a", "https://example.com"));
        assertFalse(UrlPolicy.sameOrigin("https://evil.example/a", "https://example.com"));
    }
}
