# Security Policy

## Supported Versions

We actively provide security updates for the following versions. Unlike traditional software, our SaaS envionment is continuously updated. We focus our security efforts on the live production envionment.

| Version | Supported |
| ----------------- | ------------------ |
| Production (SaaS) | :o: |
| `nightly` | :o: |
| `v5.x.x` | :o: |
| `v4` and below | :x: |

> [!IMPORTANT]
> If you are self-hosting a legacy version (`v4` or below), please migrate to the latest release, as legacy versions are no longer supported and do not receive security backports.

## Security Scope
We define the security scope based on the direct impact on our service infrastructure and operational integrity.

### In Scope

We are primarily interested in vulnerabilities that pose a direct threat to the active service, including but not limited to:

- Cross-Tenant Data Leakage: Any flaw allowing one user to view, modify, or delete another user's data.
- Access Control Breaches: Failures in authentication or authorization mechanisms that grant elevated privileges.
- Infrastructure Exposure: Flaws leading to the leakage of backend server IP addresses, internal network configurations, or environment variables.
- Remote Code Execution (RCE): Any vulnerability that allows an attacker to execute arbitrary commands on the server host.
- Service Abuse: Logic flaws that allow unauthorized resource consumptionor bypassing of usage quotas/rate limits.

### Out of Scope

The following areas are explicitly excluded from our security response and will not be processed:

- Third-party Dependencies: Vulnerabilities originating from upstream libraries or packages (e.g., those listed in `requirements.txt` or `pyproject.toml`). Please report these directly to the respective package maintainers.
- Theoretical Attacks: Reports that lack a functional proof-of-concept (PoC) or rely on highly improbable user interactions.
- Non-exploitable Best Practices: Issues such as missing security headers, descriptive error messages (without sensitive data), or lack of SRI (Subresource Integrity) unless they lead to a direct exploit.
- DDoS Attacks: General distributed denial-of-service reports, unless the attack is triggered by a specific, fixable logic flaw within the application code.

## Reporting a Vulnerability

We take the security of our project seriously. If you believe you have found a security vulnerability, please report it to us using one of the following methods. **DO NOT open a public issue for security vulnerabilities.**

### 1. Email (Preferred)
You can report vulnerabilities directly via email. You can find the maintainers' contact email address in the `pyproject.toml` file located in the root of this repository.

Please include the following information in your report:

- Description of the vulnerability
- Steps to reproduce (PoC)
- Potential impact
- Suggested fix (if any)

### 2. Instant Messaging (QQ)
For immediate discussion, you may contact the developers directly via **QQ Direct Message** for a more immediate discussion regarding the vulnerability. Note that sensitive technical details should still ideally be sent via more secure channel.

### What to Expect

- **Acknowledgement:** You will receive an acknowledgement of your report within 24–72 hours.
- **Validation**: We will investigate and notify you if the finding is valid.
- **Disclosure:** We ask that you do not disclose the vulnerability publicly until we have had the opportunity to analyze and fix the issue. 
- **Safe Harbor:** As long as you act in good faith, do not attempt to access other users' data, and do not disrupt our service, we will not pursue legal action against your research.

Thank you for helping keep this project secure!
