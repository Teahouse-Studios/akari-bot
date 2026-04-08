# Security Policy

## Supported Versions

We actively provide security updates for the following versions. We recommend all users upgrade to a supported version as soon as possible.

| Version | Supported |
| ----------------- | ------------------ |
| `nightly` | :o: |
| `v5.x.x` | :o: |
| `v4` and below | :x: |

> [!IMPORTANT]
> Versions `v4` and older are no longer supported and will not receive security patches.

## Security Scope
We define the security scope based on the direct impact on our service infrastructure and operational integrity.

### In Scope

We are primarily interested in vulnerabilities that pose a direct threat to the active service, including but not limited to:

- Infrastructure Exposure: Flaws leading to the leakage of backend server IP addresses, internal network configurations, or environment variables.
- Service Abuse: Logic flaws that allow API services to be exploited for unauthorized resource consumption, rate-limit bypassing, or unauthorized data access.
- Remote Code Execution (RCE): Any vulnerability that allows an attacker to execute arbitrary commands on the server host.
- Access Control Breaches: Failures in authentication or authorization mechanisms that grant elevated privileges.

### Out of Scope

The following areas are explicitly excluded from our security response and will not be processed:

- Third-party Dependencies: Vulnerabilities originating from upstream libraries or packages (e.g., those listed in requirements.txt or pyproject.toml). Please report these directly to the respective package maintainers.
- Theoretical Attacks: Reports that lack a functional proof-of-concept (PoC) or rely on highly improbable user interactions.
- Non-exploitable Best Practices: Issues such as missing security headers, descriptive error messages (without sensitive data), or lack of SRI (Subresource Integrity) unless they lead to a direct exploit.
- DDoS Attacks: General distributed denial-of-service reports, unless the attack is triggered by a specific, fixable logic flaw within the application code.

## Reporting a Vulnerability

We take the security of our project seriously. If you believe you have found a security vulnerability, please report it to us using one of the following methods:

### 1. Email
You can report vulnerabilities directly via email. You can find the maintainers' contact email address in the `pyproject.toml` file located in the root of this repository.

Please include the following information in your report:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### 2. Instant Messaging (QQ)
Alternatively, you may contact the developers directly via QQ **Direct Message** for a more immediate discussion regarding the vulnerability. Note that sensitive details should still ideally be sent via more secure channels.

### What to Expect

* **Acknowledgement:** You will receive an acknowledgement of your report within 24–72 hours.
* **Disclosure:** We ask that you do not disclose the vulnerability publicly until we have had the opportunity to analyze and fix the issue. 
* **Updates:** We will keep you informed of our progress as we work to resolve the reported vulnerability.

Thank you for helping keep this project secure!
