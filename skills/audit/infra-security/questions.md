# infra-security questions

What the owner states and the repository rarely shows. The axis writes the
ones its documentation does not answer as `Q-INF-<NN>`, each with the area
it settles and the answer the repository suggests; `audit-kickoff` gives
this list to a third-party owner at confirmation.

1. **Production** (all areas): where it runs (provider, region), on what
   (managed platform, virtual machines, Kubernetes, Compose), from which
   files of the repository, and what is reachable from the internet.
2. **Edge** (Edge and TLS): what terminates TLS (the application server, a
   proxy, a load balancer, a CDN), and which headers it forwards.
3. **Secrets** (Secrets delivery): how they reach production (environment,
   files, a secret manager), who can read them, when they were last rotated.
4. **Access** (Cloud and identity): who holds administrative access to the
   hosts, the cloud account, the forge and the domain; MFA enforced or not;
   shared or personal accounts.
5. **Merge and deploy** (Pipeline): what protects the default branch
   (required reviews and checks), who can merge, how a release reaches
   production (pipeline or by hand) and with which credentials.
6. **Backups** (Backups and recovery): what is backed up, how often, where
   (same provider or not), encrypted or not, kept how long, and when a
   restore was last tested.
7. **Logs and alerts** (Logging and detection): which access and
   infrastructure logs are kept, for how long, and who is alerted of what.
8. **Updates** (Images): how base images, the system and the runtime are
   kept up to date in production.
9. **Environments** (Environments): which environments exist, and whether
   they share data, credentials or networks.
