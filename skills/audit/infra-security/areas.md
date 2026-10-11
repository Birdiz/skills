# infra-security areas and severity

## Areas

- **Images**: base image origin and pinning, runtime user, what the final stage keeps, known vulnerabilities of the system and runtime, end-of-life versions, secrets in layers or build arguments.
- **Containers and orchestration**: privileges, capabilities, host mounts and the Docker socket, read-only filesystems, resource limits, health checks, restart policies.
- **Network exposure**: ports published and on which interfaces, services reachable that should not be (databases, admin APIs, mail catchers, dashboards), segmentation between services.
- **Edge and TLS**: TLS versions and certificates, redirect to HTTPS, HSTS at the edge, trust of proxies and forwarded headers, server admin interfaces.
- **Secrets delivery**: how secrets reach the runtime, defaults and fallbacks in IaC, secrets in images, CI or logs, rotation.
- **Pipeline**: CI/CD triggers and token permissions, pinning of actions and tools, secrets reachable by untrusted code, who can merge and deploy, dependency update automation.
- **Cloud and identity**: accounts and roles, least privilege, MFA, long-lived keys, storage access, network rules, encryption at rest.
- **Backups and recovery**: what is backed up, where, how often, how long, encrypted or not, restore tested.
- **Logging and detection**: infrastructure access and audit logs, how long they are kept, alerts on security events.
- **Environments**: separation of development, staging and production; development settings that reach production; credentials shared between environments.

## Severity grid

Who can reach it, and what they get:

| | Anyone on the internet | The local or hosting network, or code the pipeline runs (a dependency, an action, a pull request) | Someone already holding operator access |
|---|---|---|---|
| Control of a host, the deploy pipeline or the cloud account | critical | high | medium |
| A data store, or the secrets of a service | critical | high | low |
| Availability of the service (an exposed admin action, no resource limits) | medium | medium | low |
| Limited disclosure (versions, internal names, development data) | low | low | info |
| Hardening gap, no path shown (root user, unpinned image, broad default permission) | low | low | info |

Data that cannot be restored after an incident (no backup, or one never
restored): `high` for the stores of the main flows, `medium` for the others,
whoever causes the loss. Development-only configuration: see "Rating the
deployment" in the skill. Moves of one level: `finding-format`, Rating.
