# VLNS to VX Governed Model Activation Bridge v1

**Implementation surface:** VAIXLNS-unified  
**Canonical authority:** VAIXLNS  
**Activation boundary:** VLNS  
**Execution and evidence boundary:** VX  
**Evidence state:** PARTIAL until CI passes and a real VLNS endpoint is verified.

## 1. Boundary

The integration is federated. It does not merge VLNS, VX, or VAIXLNS identities into one system.

VAIXLNS canonical policy
→ VLNS activation gate
→ signed activation envelope
→ VLNS server activation endpoint
→ receipt bound to activation_id and envelope_hash
→ VX validates receipt and emits a traceable evidence event.

The bridge distinguishes:
- ACTIVATED_AND_RECORDED: remote receipt matches, and the evidence event is acknowledged.
- ACTIVATED_EVIDENCE_PENDING: the remote service appears to have activated the model, but evidence recording failed; promotion must stop pending reconciliation.
- RECEIPT_INVALID: receipt is missing or bound to a different request.
- REMOTE_REJECTED: the remote gate explicitly refused activation.
- TRANSPORT_FAILED: the request could not be completed.
- PREPARED_NOT_DISPATCHED: no configured server was contacted.

## 2. Contract and trust boundary

The envelope schema is in schemas/vlns-activation-envelope.schema.json. It binds:
- exact model identity, provider, and version;
- role and allowlisted capability profile;
- SHA-256 of canonical context; raw context is not copied into the envelope;
- allowlisted tools, explicit permissions, and constraints;
- provenance fields task_id, source_id, and source_digest;
- deterministic activation_id and HMAC-SHA256 signature.

The signing key must be at least 32 bytes and is supplied at runtime only. It is distinct from the HTTP bearer token. The activation_id is deterministic for identical canonical inputs and should be treated as an idempotency key by the server.

Default model-role permissions are read and propose. The activation policy prohibits external_action, canonical_write, governance_override, and unrestricted_network. Execution permission does not bypass VX policy, capability, verification, or admission gates.

## 3. Remote protocol

The client POSTs the envelope to the configured VLNS_SERVER_ACTIVATION_PATH, which defaults to /v1/activations. A successful endpoint response must be a JSON object containing:

    {
      "status": "ACTIVATED",
      "activation_id": "the exact activation_id from the request",
      "envelope_hash": "SHA-256 of the exact signed envelope"
    }

Any other status, missing field, identifier mismatch, or digest mismatch is not accepted as success.

After validating the receipt, the bridge emits VLNS_MODEL_ACTIVATION_CONFIRMED to the configured server's /events endpoint. Full success is only reported when both the activation receipt and evidence event are acknowledged. If remote activation occurred but event recording failed, the outcome is ACTIVATED_EVIDENCE_PENDING and operators must reconcile it before promotion.

This protocol is an explicit contract implemented in the client. The repository evidence does not prove that a separately hosted VLNS server implements the endpoint or receipt format.

## 4. Configuration

Configure through environment variables only. Put the SQLite evidence file on a persistent runtime volume; the default relative path is illustrative and must be adapted to the deployment:

    VLNS_SERVER_ENABLED=true
    VLNS_SERVER_URL=https://<configured-vlns-host>
    VLNS_SERVER_TOKEN=<bearer-token-from-secret-manager>
    VLNS_SERVER_HEALTH_PATH=/health
    VLNS_SERVER_ACTIVATION_PATH=/v1/activations
    VLNS_SERVER_TIMEOUT=5
    VLNS_ACTIVATION_EVIDENCE_DB=var/vx_activation_events.sqlite3
    VLNS_ACTIVATION_SIGNING_KEY=<separate-secret-of-at-least-32-bytes>
    VLNS_ALLOWED_PROVIDERS=ollama,openai-compatible
    VLNS_ALLOWED_CAPABILITIES=reasoning,research,engineering,verification
    VLNS_ALLOWED_TOOLS=repository.read,web.search

Never commit secrets or print them in logs. An absent or disabled server does not fall back to a fictitious local success.

## 5. Runnable path

Prepare a JSON request file using the fields from ActivationRequest, including context_payload and provenance. Then run:

    python scripts/vlns_activation_bridge.py request.json --prepare-only
    python scripts/vlns_activation_bridge.py request.json
    python -m pytest -q tests/test_vlns_activation_bridge.py

The prepare-only mode validates policy and prints a signed non-dispatched envelope. The dispatch command exits successfully only for ACTIVATED_AND_RECORDED. Tests use local fakes and do not contact an external system.

## 6. Admission and truth boundary

This change implements a deterministic activation contract, local policy checks, a signed envelope, a receipt-verifying HTTP bridge, and evidence-event acknowledgement. It does not by itself establish:
- a live network route to a VLNS server;
- authentication or compatibility of an unknown server;
- that VLNS and NAXLNS are the same repository/system identity;
- production deployment or operational readiness;
- model quality or authority to execute arbitrary tools.

Required remaining gates are repository identity evidence, endpoint identity/authentication, sandbox verification, functional and rejection-path tests, failure/recovery, replay, independent verification, proof freshness, explicit authority, admission, and continuous revalidation.


## 7. Specialist-agent provider integration

The companion reference gate is maintained in the separate vx-agents-fabric repository to preserve source ownership:

- Source branch: https://github.com/fisallllll280-code/vx-agents-fabric/tree/feat/vlns-provider-adapter-20261009
- Gate module: src/vx_agents_fabric/vlns_activation.py
- Provider factory: src/vx_agents_fabric/providers/factory.py
- Tests: tests/test_vlns_activation.py
- CI evidence: https://github.com/fisallllll280-code/vx-agents-fabric/actions/runs/37915189114

When VX_VLNS_ACTIVATION_REQUIRED=true, specialist agent calls and independent parent-review minds must obtain a matching remote activation receipt and append a hash-linked event to the local VX evidence journal before model inference. Failure returns HOLD and the provider is not invoked. The journal path is configured by VX_VLNS_EVIDENCE_DB. The gate is optional for legacy compatibility; any deployment claiming VLNS-governed model execution must enable it explicitly and must not claim production readiness solely because its local tests pass.

The agent-fabric gate branch is CI-green but is not merged into the default branch. Its local SQLite journal is a separate evidence source; automatic federation of that journal into the canonical VAIXLNS store is still required for a single cross-repository ledger. Neither this code nor local tests establish live connectivity or resolve the VLNS↔NAXLNS identity.
