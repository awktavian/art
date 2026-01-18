# Security Policy

## Supported Versions

We release security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.1.x   | :white_check_mark: |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

### Reporting Process

1. **Email**: Send details to security@kagami.ai (if available) or create a private security advisory on GitHub
2. **Include**:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)
3. **Response Time**: We aim to respond within 48 hours

### What to Expect

1. **Acknowledgment**: We'll confirm receipt within 48 hours
2. **Assessment**: We'll assess the vulnerability within 7 days
3. **Updates**: We'll provide regular updates on progress
4. **Fix**: We'll work on a fix and coordinate disclosure
5. **Credit**: We'll credit you in the security advisory (if desired)

## Security Update Process

### Timeline

- **Critical vulnerabilities**: Patch within 7 days
- **High severity**: Patch within 30 days
- **Medium severity**: Patch within 90 days
- **Low severity**: Patch in next regular release

### Disclosure

- We practice **coordinated disclosure**
- Security advisories published after patch is released
- CVE IDs assigned for significant vulnerabilities

## Security Best Practices

### For Users

#### Production Deployment

1. **Secrets Management**
   ```bash
   # Never use default secrets
   # Generate strong secrets:
   python -c "import secrets; print(secrets.token_urlsafe(32))"

   # Use secret management systems:
   - AWS Secrets Manager
   - HashiCorp Vault
   - Azure Key Vault
   - GCP Secret Manager
   ```

2. **Environment Variables**
   ```bash
   # Required security settings:
   ENVIRONMENT=production
   DEBUG=false
   JWT_SECRET=<strong-random-32+chars>
   CSRF_SECRET=<strong-random-32+chars>

   # Never commit .env files!
   ```

3. **Database Security**
   ```bash
   # Use TLS for database connections
   DATABASE_URL=postgresql://user:pass@host:5432/db?sslmode=require

   # Never use localhost in production
   # Never use default passwords
   ```

4. **API Security**
   ```bash
   # Enable rate limiting
   RATE_LIMIT_ENABLED=true

   # Use strong API keys
   # Rotate keys regularly (quarterly)
   ```

#### Network Security

- Use TLS 1.3 for all connections
- Enable HSTS headers
- Configure proper CORS policies
- Use security headers (CSP, X-Frame-Options, etc.)

#### Authentication

- Use JWT with strong secrets (32+ characters)
- Enable CSRF protection
- Implement rate limiting on auth endpoints
- Use secure password hashing (bcrypt with cost factor 12+)

### For Developers

#### Code Security

1. **Input Validation**
   ```python
   # Always validate user input
   from pydantic import BaseModel, Field

   class UserInput(BaseModel):
       text: str = Field(..., max_length=1000)
       email: str = Field(..., regex=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
   ```

2. **SQL Injection Prevention**
   ```python
   # Use parameterized queries
   # Good ✅
   cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))

   # Bad ❌
   cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
   ```

3. **XSS Prevention**
   ```python
   # Escape output
   from markupsafe import escape
   safe_output = escape(user_input)
   ```

4. **CSRF Protection**
   ```python
   # Already implemented in kagami/api/middleware/csrf_protection.py
   # Ensure it's enabled for all state-changing endpoints
   ```

5. **Secrets in Code**
   ```python
   # Never hardcode secrets
   # Good ✅
   secret = os.getenv("JWT_SECRET")

   # Bad ❌
   secret = "my-secret-key-12345"
   ```

#### Dependency Security

```bash
# Regularly audit dependencies
pip-audit
safety check

# Keep dependencies updated
pip list --outdated
```

#### Security Testing

```bash
# Run security tests
make security-test

# Static analysis
bandit -r kagami/
```

## Known Security Features

### Control Barrier Functions (CBF)

Kagami implements formal safety guarantees using Control Barrier Functions:

- **h(x) ≥ 0 enforcement**: All actions must satisfy safety constraints
- **Jailbreak detection**: Attempts to bypass safety systems are detected
- **Memory hygiene**: Prevents unauthorized memory access
- **Content boundaries**: Enforces ethical boundaries

### Authentication & Authorization

- JWT-based authentication with refresh tokens
- Role-Based Access Control (RBAC)
- API key management with rotation
- Multi-factor authentication support (TOTP)

### Network Security

- TLS enforcement for all connections
- CSRF protection with double-submit cookies
- Rate limiting (token bucket + sliding window)
- Input validation middleware

### Data Protection

- Encryption at rest for sensitive data
- Signed serialization for anti-replication
- Audit logging for security events
- Data retention policies

## Security Contact

- **Email**: security@kagami.ai
- **PGP Key**: [Link to public key]
- **GitHub**: Security Advisories on repository

## Security Advisories

Past security advisories are published at:
- GitHub Security Advisories
- [Security page on website]

## Bug Bounty Program

We currently do not have a formal bug bounty program, but we recognize and credit security researchers who responsibly disclose vulnerabilities.

## Compliance

Kagami is designed with compliance in mind:

- **GDPR**: Data export and deletion capabilities
- **SOC 2**: Audit logging and access controls
- **HIPAA**: Encryption and access controls (when configured)

## Security Changelog

### Version 1.1.0 (2025-12-21)
- Enhanced CBF safety enforcement
- TLS enforcement across all services
- Secret rotation policy implementation
- Rate limiting improvements

### Version 1.0.0 (2025-12-26)
- Initial release with safety systems
- JWT authentication
- RBAC implementation
- CSRF protection

## Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)

---

**Last Updated**: December 28, 2025

Thank you for helping keep Kagami secure! 🔒
