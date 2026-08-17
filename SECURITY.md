# Security policy

## Supported version

Only the latest release receives security fixes.

## Reporting a vulnerability

Do not open a public issue containing credentials or exploit details. Use GitHub's private vulnerability reporting feature for the repository. Include the affected version, impact, and minimal reproduction. Remove provider keys, access tokens, personal conversation data, and sandbox contents from logs before sharing them.

## Deployment boundaries

TUESDAY is a single-owner service. Keep `TUESDAY_ACCESS_TOKEN` private, use the supplied PostgreSQL service, and use E2B rather than the local sandbox in production. Provider credentials belong only in Render's secret environment variables. If a credential is exposed, revoke it at the provider before changing the deployment.
