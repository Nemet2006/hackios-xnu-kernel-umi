# A32 UEFI bring-up

This platform is based on the BSD-2-Clause-Patent licensed
[uefi-merlinx](https://github.com/Dracen-W/uefi-merlinx) source at the commit
in `BASE`. It selects the shared MT6768 family's MT6769T variant, Samsung
SM-A325F identity, 1080 x 2400 display geometry and this phone's stock
Android boot image addresses. The copied keypad library has **not** been
verified on A32 hardware.

`a32Pkg/Library/MemoryMapLib` builds the early memory map from LK's incoming
FDT before SEC enables the MMU. It subtracts fixed `/reserved-memory` ranges,
FDT reserve-map entries, the FDT itself, initrd, framebuffer and the UEFI
stack/FD/heap. It refuses to continue if the live tree exposes less than
2.5 GiB of usable RAM. The framebuffer reservation is exposed to the existing
SimpleFb GOP driver. `A32BootMemoryDxe` then publishes the initrd as a
read-only block device. The inherited Redmi Note 9 free-RAM table is removed.

This path has passed a host firmware build but has not run on A32 hardware.
The Android static DTB is incomplete, so it is expected to fail closed when
used in place of LK's live FDT.

To stage the sources in the pinned local checkout:

```sh
devices/a32/uefi/apply.sh
```

After the local UniXNU feeds and LLVM 18 toolchain are prepared, compile with
`devices/a32/uefi/build-local.sh`. The resulting host artifact is
`out/a32/reference-uefi-merlinx/Build/a32Pkg/DEBUG_CLANGPDB/FV/SILICIUM_UEFI.fd`.
The A32 package compiled successfully on 2026-10-30; the 3 MiB volume has not
been run on the phone.

`devices/a32/uefi/package-bootimg.sh` packages that volume with the stock base
DTB and the XNUP payload into `out/a32/boot-a32-diagnostic.img`. It checks the
image against the stock boot header and rejects an image larger than the
32 MiB boot partition. This verifies host-side packaging only; it does not
flash or boot the image, and Samsung download-mode acceptance is untested.

The source still requires a phone boot test of the early FDT map and display
handoff. The stock DTB alone is incomplete: Linux reports RAM above 4 GiB
that the stock `/memory` node does not describe. The phone's unprivileged ADB
shell cannot read the live FDT or `/proc/iomem`.
