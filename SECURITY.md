# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅ Current |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do NOT** open a public GitHub issue
2. Email **vi89012@gmail.com** with:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
3. You will receive an acknowledgment within **48 hours**
4. We will work with you to understand and address the issue
5. A fix will be released as soon as possible, and you will be credited (unless you prefer otherwise)

## Scope

### In scope

- Authentication / authorization bypasses
- Remote code execution
- SQL injection or NoSQL injection
- Cross-site scripting (XSS)
- Server-side request forgery (SSRF)
- Sensitive data exposure

### Out of scope

- Anti-bot bypass techniques (this is core functionality, not a vulnerability)
- Denial of service via excessive API calls (mitigated by rate limiting)
- Issues in third-party dependencies (report upstream, but let us know too)
- Social engineering attacks

## Best Practices

This project follows security best practices:

- Non-root Docker containers
- CORS lockdown (configurable origins)
- Rate limiting via slowapi
- Input validation via Pydantic schemas
- No secrets committed to the repository
