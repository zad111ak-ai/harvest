# Security Policy

## Reporting a Vulnerability

**NEVER create a public issue for security vulnerabilities!**

📧 Email: [REDACTED]
🔒 GPG Key: Available on request

We will respond within 48 hours.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x.x   | ✅ Active |
| 0.x.x   | ❌ Deprecated |

## Security Best Practices

- Keep dependencies updated
- Use virtual environments
- Never commit secrets or API keys
- Run with minimal privileges
- Use HTTPS for all external requests

## Dependencies

We regularly audit dependencies for vulnerabilities using:
- `pip-audit`
- GitHub Dependabot
- Manual review

## Data Privacy

Harvest processes data locally. No data is sent to external services unless explicitly configured by the user.
