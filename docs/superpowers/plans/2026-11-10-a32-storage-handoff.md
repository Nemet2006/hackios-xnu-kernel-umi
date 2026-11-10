# A32 storage handoff guard and early checkpoint preparation

> Execute inline with superpowers:executing-plans. Preserve uncommitted work; no delegation or commits.

**Goal:** Refuse mailbox storage on the loader CPU and prepare a bounded host-only early-XNU probe.
**Architecture:** Normalize the self-test CPU before checking storage eligibility in run_kernel. Reject ufs=2 on the current CPU before charger/storage operations. Reuse existing early assembly checkpoint for the probe.
**Tech Stack:** Freestanding C, Python production-code harness, UBSan, AArch64 EFI toolchain.
**Spec:** devices/a32/STORAGE-INTEGRATION-AUDIT.az.md and user's instruction to proceed.

- [x] Extract real CPU/argument/service dispatch block into a host harness; demonstrate same-CPU rejection failure, different-CPU acceptance, no-storage/survey behavior, selftest override.
- [x] Add guard before hardware-service dispatch, normalize selftest first, run all A32 host tests and both loader builds.
- [x] Inspect earliest checkpoint and prepare a separate payload from current kernel without storage/native/write/SMP requests. Verify checkpoint, embedded kernel identity and record prerequisites. No flash/unlock/reboot.
- [x] Self-review and update checkpoint with results and remaining runtime constraints.

The early probe must not silently load a full system.apfs. Retain existing artifacts and avoid claiming a host build is a phone boot.

Execution: 9 A32 scripts and both loader builds passed. RED/GREEN and artifact evidence in out/a32/handoff-guard-2026-11-10/. Self-review only under no-delegation preference. The guard runs before service initialization, but after existing window allocation/kernel copying; it is not a rollback mechanism. No image was flashed or packaged.
