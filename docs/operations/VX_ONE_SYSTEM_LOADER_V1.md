# VX ONE — System Loader & Boot Preparation v1

**Status:** IMPLEMENTED CANDIDATE (manifest validation and local preflight code only)  
**Execution status:** NOT RUN IN THIS CHANGE; no image download, disk write, boot-media creation, OS installation, firmware change, or reboot  
**Authority:** VAIXLNS contracts and governance  
**Execution boundary:** VX  
**Initial implementation surface:** VAIXLNS-unified  
**Default posture:** local manifest validation, no network, plan-only, fail-closed

## 1. Purpose

VX ONE is the single system-loading and boot-preparation path for the VAIXLNS repository family. It is not a new operating system and it is not a replacement UEFI firmware boot manager. It coordinates declared operating-system images, installers, recovery images, and runtime bundles through a common manifest and evidence contract.

The first vertical slice intentionally implements only:
- strict manifest validation;
- official-source host allowlisting;
- artifact size and SHA-256 comparison;
- an injected Ed25519 signature-verification boundary;
- a reviewable preflight plan;
- explicit rejection of installation execution in v1.

It does **not** implement an OS downloader, disk partitioner, EFI bootloader binary, USB writer, installer, firmware editor, or reboot service.

## 2. Existing assets and no-parallel-system decision

The repository already contains:
- `operations/boot_controller.py`: application readiness gate;
- `integration/boot.py`: federated smoke/conformance runner;
- `operations/recovery_engine.py`: existing recovery surface;
- a broader federation/continuity contract.

VX ONE extends these assets conceptually. It must not duplicate the existing boot controller or treat the current smoke runner as a machine bootloader.

## 3. Architecture

```text
VAIXLNS System Catalog / Repository Manifests
                  |
                  v
       VX ONE Manifest Registry
                  |
                  v
     DISCOVER -> IDENTIFY -> SCAN
                  |
                  v
       Compatibility / Risk Preflight
                  |
                  v
       SHA-256 + Signature Verification
                  |
                  v
        Human Approval / Admission
                  |
                  v
      [future separately authorized adapter]
         Download -> Stage -> Boot Media
                  |
                  v
       UEFI Secure Boot / Trusted Boot
                  |
                  v
       TPM Measured Boot / Attestation
                  |
                  v
        Post-boot Health / Evidence
```

## 4. Manifest contract

Every bootable or installable artifact must declare:
- stable system and artifact IDs;
- semantic version and target OS/architecture;
- firmware compatibility (UEFI/BIOS);
- official HTTPS source host;
- exact byte size and SHA-256;
- detached Ed25519 signature and signer identity;
- policy requiring human approval;
- network and install execution disabled by default.

The JSON Schema is `schemas/vx-system-manifest.v1.schema.json`. The initial discovery catalog is `config/vx-system-loader.catalog.v1.json`; entries intentionally have no artifact URL or digest yet and therefore cannot be downloaded or admitted.

## 5. Security model

### Secure Boot
Use platform UEFI Secure Boot to authenticate boot executables. VX must not silently enroll keys, replace firmware trust databases, disable Secure Boot, or assume every device supports the same key workflow.

### Measured Boot
Where supported, capture TPM measurements and event logs. Measured Boot is evidence/attestation, not a substitute for Secure Boot enforcement. Remote attestation requires a separately configured verifier and trust policy.

### Artifact authenticity
SHA-256 detects content mismatch but does not prove publisher identity. The injected signature verifier must validate Ed25519 signatures against independently pinned vendor/release keys. No trust key is embedded in this initial implementation.

### Supply chain
Manifest, image, signature, source, and policy versions must be pinned and retained. Redirects and arbitrary mirror hosts are not allowed in the v1 source policy. A future downloader must independently revalidate the final host, digest, size, and signature after transfer.

### Destructive actions
Disk selection, partitioning, formatting, EFI variable changes, Secure Boot key enrollment, TPM ownership changes, and reboot require distinct target-specific approval gates. No broad "install" permission may imply these actions.

## 6. Lifecycle and status semantics

```
DISCOVERED
 -> IDENTIFIED
 -> SCANNED
 -> SIMULATED
 -> VERIFIED_FOR_REVIEW
 -> HUMAN_APPROVED
 -> STAGED
 -> BOOT_MEDIA_READY
 -> BOOT_OBSERVED
 -> POST_BOOT_VERIFIED
```

Any failed or missing check results in `BLOCKED` or `NOT_OBSERVED`, not a success claim. `VERIFIED_FOR_REVIEW` means the manifest, size, digest, and injected signature verifier passed; it does not mean installation is approved or that the image booted.

## 7. Repository federation

The intended division of responsibility is:
- **VAIXLNS:** canonical system identity, source policy, manifest contracts, governance and evidence requirements.
- **VAIXLNS-unified:** shared catalog, manifest validation, preflight and user-facing orchestration.
- **VX-runtime:** isolated execution adapters, verification receipts, rollback and post-boot observation.
- **NEXENT:** system discovery, compatibility research, dependency intelligence and candidate generation.

A repository may carry a manifest or adapter declaration, but it must not ship an independently competing loader. All repositories must reference the same schema version and lifecycle contract. Cross-repository integration is not yet verified.

## 8. Acceptance tests

The v1 test suite checks:
1. valid allowlisted HTTPS manifest;
2. HTTP rejection;
3. unknown host rejection;
4. credentials/fragments rejection;
5. duplicate artifact rejection;
6. mandatory human approval;
7. network and installation execution disabled;
8. hash and size matching;
9. fail-closed behavior when no signature verifier exists;
10. injected signature-verifier path;
11. unknown artifact rejection;
12. explicit rejection of install execution.

Run locally from the repository root:

```bash
python -m unittest tests.test_vx_system_loader -v
```

## 9. Next implementation gates

- **G0 — Baseline:** inventory all existing boot, installer, recovery and platform adapter assets.
- **G1 — Catalog:** populate vendor artifact manifests only from verified official release metadata.
- **G2 — Trust roots:** independently pin and rotate vendor signing keys; implement a production Ed25519 verifier.
- **G3 — Download adapter:** bounded HTTPS downloader with redirects disabled, size caps, resumable partial files, quarantine staging, and post-download digest/signature revalidation.
- **G4 — Media preparation:** platform-specific UEFI/BIOS media creation in disposable test images/VMs first; no physical disk writes.
- **G5 — Boot simulation:** QEMU/OVMF test matrix, Secure Boot on/off cases, TPM emulation, failure injection and rollback.
- **G6 — Windows/Linux compatibility:** separate tested profiles; no claim of universal support.
- **G7 — Human admission:** explicit per-device target, disk, data-loss acknowledgement and approval receipt.
- **G8 — Real hardware pilot:** only after independent security review and separate explicit authorization.

## 10. Protected boundaries

- `project.genome` and `Ω.000` are not modified.
- No main-branch changes, merges, deployments, external service connections, or spending are part of this candidate.
- No image is downloaded and no host device is modified.
- No automatic disk erase, partition, firmware mutation, TPM reset, key enrollment, or reboot.
- Failed candidates and their evidence must be retained; no silent cleanup or history rewrite.

## 11. References

- systemd: Boot Components & Root File System Discovery — https://github.com/systemd/systemd/blob/main/docs/ROOTFS_DISCOVERY.md
- systemd-boot — https://github.com/systemd/systemd/blob/main/docs/BOOT.md
- Microsoft: Secure the Windows boot process — https://learn.microsoft.com/en-gb/windows/security/operating-system-security/system-security/secure-the-windows-10-boot-process
- NSA: Boot Security Modes and Recommendations — https://www.nsa.gov/portals/75/documents/resources/cybersecurity-professionals/csi-boot-security-modes-and-recommendations.pdf

**Claim boundary:** this document and code define a candidate loader preflight. They do not establish a working bootable USB, successful OS installation, Secure Boot attestation, or successful boot on physical hardware.
