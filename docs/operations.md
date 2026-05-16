# Operations Runbook: Secret Management and Key Rotation

## Overview
This runbook formalises how we manage application secrets in production. The API
now reads its runtime configuration from [HashiCorp Vault](https://www.vaultproject.io/)
whenever `VAULT_ENABLED=true`. Vault stores all sensitive credentials,
including external LLM access tokens and safety model keys, inside the KV v2
engine at `kv/avi/production`.

The runtime sequence is:

1. The service starts with Vault connectivity variables exported as
   environment variables.
2. `config.settings.Settings.apply_vault_overrides()` authenticates to Vault
   via AppRole and downloads the secrets stored at the configured path.
3. The settings object overrides local values with Vault data **before** the
   rest of the application initialises, so no secrets are ever committed to the
   repository or .env files on the server.

## Preparing Vault
1. Enable the KV v2 engine (if not already enabled):
   ```bash
   vault secrets enable -path=kv kv-v2
   ```
2. Create a policy with read-only access to the production secret path:
   ```hcl
   path "kv/data/avi/production" {
     capabilities = ["read"]
   }
   ```
3. Load the policy into Vault:
   ```bash
   vault policy write avi-production ./avi-production.hcl
   ```
4. Provision an AppRole with the policy attached:
   ```bash
   vault write auth/approle/role/avi-api \
     token_policies="avi-production" \
     token_ttl=24h token_max_ttl=72h

   vault read auth/approle/role/avi-api/role-id
   vault write -f auth/approle/role/avi-api/secret-id
   ```
   Save the resulting `role_id` and `secret_id` in a secure password manager.

## Deploying the Secret Retrieval Flow on Servers
1. **Bootstrap environment variables** inside the systemd unit (or container
   orchestrator) that runs the API:
   ```ini
   Environment="VAULT_ENABLED=true"
   Environment="VAULT_ADDR=https://vault.example.com"
   Environment="VAULT_NAMESPACE=avi"
   Environment="VAULT_AUTH_METHOD=approle"
   Environment="VAULT_ROLE_ID=<role_id>"
   Environment="VAULT_SECRET_ID=<secret_id>"
   Environment="VAULT_MOUNT_POINT=kv"
   Environment="VAULT_SECRETS_PATH=avi/production"
   ```
   Never store these values in shell history—use `systemctl edit` or the
   orchestration secrets store.
2. **(Optional) Refresh the SecretID automatically.** For AppRole, configure a
   cron job that requests a new SecretID daily and updates the deployment
   secret store:
   ```bash
   vault write -f auth/approle/role/avi-api/secret-id \
     | jq -r .data.secret_id > /etc/avi/vault_secret_id
   ```
   Grant read permission on `/etc/avi/vault_secret_id` only to the service
   account running the API.
3. **Validate connectivity** from the host before starting the service:
   ```bash
   VAULT_ADDR=https://vault.example.com \
   VAULT_NAMESPACE=avi \
   vault login -method=approle role_id=$VAULT_ROLE_ID secret_id=$VAULT_SECRET_ID
   vault kv get kv/avi/production
   ```
   The `kv get` command should return the JSON payload with all application
   secrets.

## Application Configuration
When the service starts in production, the following environment variables must
be present:

- `VAULT_ENABLED=true`
- `VAULT_ADDR=https://vault.example.com`
- `VAULT_NAMESPACE=avi` (omit if namespaces are disabled)
- `VAULT_AUTH_METHOD=approle`
- `VAULT_ROLE_ID` and `VAULT_SECRET_ID`
- `VAULT_MOUNT_POINT=kv`
- `VAULT_SECRETS_PATH=avi/production`

The Vault document stored at `kv/avi/production` should contain key-value pairs
for each configuration field listed in `Settings.VAULT_SYNC_FIELDS`. Example
payload:

```json
{
  "MAIN_LLM_API_KEY": "sk-prod-...",
  "MAIN_LLM_API_BASE": "https://llm.vendor/api",
  "MAIN_LLM_MODEL": "vendor-large-2024",
  "SAFETY_LLM_API_KEY": "safety-prod-...",
  "SAFETY_LLM_API_BASE": "https://safety.vendor/api",
  "SAFETY_LLM_MODEL": "safety-guard-2",
  "SCORING_LLM_API_KEY": "score-prod-..."
}
```

Any value defined in Vault overrides whatever is provided through `.env` or
process environment variables. Local development remains unchanged; simply omit
`VAULT_ENABLED`.

## Rotating Main LLM and Safety Model Keys
Follow this playbook to rotate keys without downtime:

1. **Request new credentials** from the vendor portals for both the main LLM
   and the safety model. Ensure the old keys stay valid during the transition.
2. **Update Vault** with the new values:
   ```bash
   vault kv patch kv/avi/production \
     MAIN_LLM_API_KEY="sk-new-..." \
     SAFETY_LLM_API_KEY="safety-new-..." \
     SCORING_LLM_API_KEY="score-new-..."
   ```
   Include any accompanying base URLs or model identifiers if they changed.
3. **Trigger a configuration reload**:
   - For rolling deployments (Kubernetes, Nomad) simply restart the pods.
   - For systemd services run `systemctl restart avi-api`.
   On restart the application fetches the new secrets automatically.
4. **Decommission old keys** once the deployment confirms successful
   authentication. Revoke the superseded credentials in the vendor consoles to
   prevent accidental reuse.
5. **Document the rotation** in the operations log (Confluence or the shared
   runbook) with the date, operator, and confirmation links.

## Team Enablement Checklist
To bring engineers and on-call staff up to speed:

1. **Hands-on session:** Pair with each engineer to walk through
   `vault login` and `vault kv get kv/avi/production` using a sandbox role.
2. **Distribute this document** via the team knowledge base and post a link in
   the `#avi-platform` Slack channel.
3. **Access review:** Verify that only on-call engineers and the CI/CD service
   accounts have access to the AppRole credentials. Rotate or revoke any unused
   credentials during quarterly security reviews.
4. **Tabletop exercise:** Once per quarter, simulate a compromised key. The
   drill should follow the rotation playbook above and verify that monitoring
   captures the credential change.

By following this runbook, the team can safely retrieve secrets at runtime,
rotate credentials on demand, and maintain a consistent operational posture.
