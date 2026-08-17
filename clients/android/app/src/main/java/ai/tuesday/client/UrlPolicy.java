package ai.tuesday.client;

import java.net.URI;
import java.net.URISyntaxException;

final class UrlPolicy {
    private UrlPolicy() {}

    static String normalizeBackend(String raw, boolean allowLocalHttp) {
        if (raw == null) return null;
        String value = raw.trim();
        if (value.endsWith("/")) value = value.substring(0, value.length() - 1);
        try {
            URI uri = new URI(value);
            String scheme = uri.getScheme();
            String host = uri.getHost();
            boolean local = "localhost".equalsIgnoreCase(host)
                    || "127.0.0.1".equals(host)
                    || "10.0.2.2".equals(host);
            boolean schemeAllowed = "https".equalsIgnoreCase(scheme)
                    || (allowLocalHttp && local && "http".equalsIgnoreCase(scheme));
            if (!schemeAllowed || host == null || uri.getUserInfo() != null
                    || uri.getQuery() != null || uri.getFragment() != null
                    || (uri.getPath() != null && !uri.getPath().isEmpty())) {
                return null;
            }
            return uri.toString();
        } catch (URISyntaxException error) {
            return null;
        }
    }

    static boolean sameOrigin(String candidate, String backend) {
        try {
            URI left = new URI(candidate);
            URI right = new URI(backend);
            return left.getScheme().equalsIgnoreCase(right.getScheme())
                    && left.getHost().equalsIgnoreCase(right.getHost())
                    && effectivePort(left) == effectivePort(right);
        } catch (RuntimeException | URISyntaxException error) {
            return false;
        }
    }

    private static int effectivePort(URI uri) {
        if (uri.getPort() >= 0) return uri.getPort();
        return "https".equalsIgnoreCase(uri.getScheme()) ? 443 : 80;
    }
}
