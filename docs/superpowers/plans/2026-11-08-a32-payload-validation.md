# A32 Payload Canonical Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline. Preserve the user's no-delegation and no-auto-commit preferences.

**Goal:** Reject noncanonical volume-loaded payloads before banner/parser visibility, matching the host verifier's structural rules.
**Architecture:** Keep the existing XNUP format and volume-load ownership lifecycle. Extend the existing production-function harness with file fixtures; only EFI I/O is stubbed. Bound duplicate checks with a 128-entry limit in both host and runtime volume validation.
**Tech Stack:** Freestanding AArch64 C, Python 3, host C harness, UBSan, Clang/lld-link.
**Spec:** `docs/superpowers/specs/2026-11-08-a32-validation-design.md` (approved).

## Global Constraints

- Preserve existing uncommitted work; no automatic commits or branch integration.
- No device flash, unlock, erase, repartition or reboot in this payload stage.
- Generic/preloaded path stays distinct; no A32 platform/kernel requirement added to generic volume validation.
- One failing fixture category followed by its minimal production fix, then the full local A32 suite.
- 128 ordinary entries maximum, excluding the terminal entry; unknown ASCII entry names remain accepted within this bound. Fixed stack storage only for duplicate detection. This cap is an implementation choice to bound work, not a pre-existing wire-format rule.
- Do not claim full UTF-8/numeric semantic parity or hardware boot success.

## Review Focus

- Terminator with hidden name bytes must not publish payload state (Task 1).
- Unknown extension entry names must still load when canonical (Task 1/3).
- Invalid payload must free pages and leave banner inaccessible, including after a prior successful load (existing lifecycle + Task 1).
- Duplicate unknown names and the exact entry-count boundary must behave identically (Task 3).
- Generic payload without A32 platform policy remains volume-loadable (Task 3).

### Task 1: Canonical names and terminator at the volume boundary

**Files:** Modify `devices/a32/tools/test-loader-volume.py`, `xnuloader/loader.c`.
**Interfaces:** Existing `load_payload_from_volume(void)` returns 0 and keeps `payload_readable=0` on malformed input; existing `inspect(bytes)` rejects the same fixture. No new production API.

- [x] Extend current harness to accept a file fixture and expected outcome, while retaining all 8 original scenarios. In Python, import the actual host verifier and generate a minimal A32 fixture with kernel bytes and explicit expected results.
- [x] Add nonzero name tail, terminator hidden name byte, and non-ASCII name cases one category at a time. Run `python3 devices/a32/tools/test-loader-volume.py`: each new bad category must initially be accepted by runtime and make the expectation fail, while host rejects it.
- [x] Reject nonzero name suffix, non-ASCII name bytes and nonzero terminal name bytes in `volume_payload_valid`. Re-run the test after each minimal change; expected PASS and correct cleanup.
- [x] Preserve accepted unknown ASCII extensions and normal empty/nonempty text conventions. Record RED/GREEN evidence; no commit.

### Task 2: Padding and embedded text terminators

**Files:** Same two files.
**Interfaces:** Same load/visibility seam and host verifier.

- [x] Add nonzero data padding fixture, observe runtime rejection assertion fail, then check padding in production; rerun to PASS.
- [x] Add embedded NUL text fixture, observe runtime rejection assertion fail, then reject NUL before the final terminator; rerun to PASS.
- [x] Add valid empty text, aligned binary payload containing zero/high bytes, and unchanged malformed length/read regressions. Empty text remains a single terminating zero; arbitrary binary data remains unrestricted.
- [x] Record RED/GREEN evidence; no commit.

### Task 3: Bounded duplicate detection and complete verification

**Files:** Above plus `devices/a32/tools/verify-payload.py`, `devices/a32/LOADER-AUDIT.az.md`, `CHECKPOINT-A32.md`.
**Interfaces:** Runtime and host accept up to 128 unique ordinary entries and reject the 129th. Terminator is not counted. Known/unknown duplicate names are rejected. Runtime uses fixed-size name-pointer storage; no new heap allocation.

- [x] Add duplicate-known and duplicate-unknown fixtures, watch runtime wrongly accept, then implement bounded name tracking with zero allocation; rerun to PASS.
- [x] Add 128/129 unique-entry boundary cases. Watch host accept 129, then impose the same host limit. Test canonical extension names and generic no-platform payload separately from A32 host policy.
- [x] Review checkpoint parsing and UTF-8 differences and document remaining scope instead of silently changing generic number parsing.
- [x] Run all `devices/a32/tools/test-*.py`; expected PASS. Run current payload host verifier with checkpoint 0; expected PASS.
- [x] Build A32 and generic EFI with the existing local toolchain; expected exit 0. Preserve baseline artifact/source hashes; save final hashes and logs under `out/a32/payload-validation-2026-11-08/`.
- [x] Run available repository host regression scripts; report unavailable dependency fixtures or unrelated baseline failures by name. Review diff against session baseline, update audit/checkpoint, leave changes uncommitted.

## Execution rulings

The user has approved execution and test seams; no repeated approval request for routine steps. Continue in the existing `codex/a32-memory-handoff-20261107` checkout because the approved design preserves the dirty A32 source/build workspace. Snapshot affected files first; do not create a clean worktree that omits untracked A32 dependencies. Self-review replaces delegated review under the preserved no-delegation preference.
