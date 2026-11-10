# SM-A325F boot investigation

## Inputs and validation

The connected phone reports build and bootloader `A325FXXSCDXL2`,
`ro.boot.revision=4`, platform `mt6768`, hardware `mt6769t`.
Its reported carrier ID is `CAU`; the supplied product code ends in XSG.
The matching XSG package was downloaded from Samsung FUS using
samloader-rs 2.2.0. Firmware version:
`A325FXXSCDXL2/A325FOJMCDXL2/A325FXXSCDXL2/A325FXXSCDXL2`.

Host-only artifacts are under `out/a32/stock/` (git ignored).
The archive is `SM-A325F_3_20241230123541_brfp5arl3v_fac.zip`.
`tools/extract-stock.py` reads its AP archive and decompresses selected images.
It was checked with a small fixture and the actual downloaded archive.

| Image | Bytes | SHA-256 |
|---|---:|---|
| boot.img | 33554432 | 0532ceeb814428b580a5320d8b2f5898a3580f4453d4d5be256b37a922df4745 |
| recovery.img | 33554432 | 82f0b608bf7293a3f8e64c37fc0dbae03c87aef602ecf8cb23e64b5f2292b082 |
| dtbo.img | 256800 | fd6ae6a784d1dd674a3628e1b79b9f992f7b638782d02aed36039b5824dd77b9 |
| lk-verified.img | 2097152 | 779ef120a1947b1c51c9fc2cf746a6dd23587878cbdd3337fa41ebddfb311a07 |

`lk-verified.img` was extracted from the matching BL archive. Its strings
include `fastboot_init`, `cmd_boot`, `Entering fastboot mode`, and Samsung
`ODIN MODE`; these establish that related code exists in the binary, not that
this retail device exposes a usable `fastboot boot` USB mode. A real USB-mode
test is required before relying on a reversible boot workflow.

The matching CSC archive contains `A32_EUR_OPEN.pit` (SHA-256
`459bd945426b61efaaf73733506d7661bc4be8fc11d7ff50dcc44b87ab399`).
Heimdall 2.1.0 parsed 54 entries. The package PIT's `boot` entry is identifier 36,
offset 1162448 sectors, length 65536 sectors (32 MiB); this agrees with the
ADB symlink to `mmcblk0p36` and the 32 MiB stock image. The `lk` entry is
identifier 12 and `dtbo` is 13, also matching ADB. The live PIT read over
Download Mode reported the same entry count, chipset tag, and boot partition
size.

On 2026-10-31, `adb reboot download` exposed the phone to Heimdall as USB
`04e8:685d`; Heimdall detected it and `print-pit` read a live 54-entry PIT
tagged `MTK6769T`, including the 32 MiB `boot` entry. A later `flash --BOOT`
attempt failed while opening its protocol session, before Heimdall reported a
write. No image was flashed. Heimdall's `--no-reboot`/resume sequence left the
phone in Download Mode and requires a physical Volume Down + side/power
button hold to return to Android before retrying a clean session.

For diagnosis, the host USB device was reset with `usbreset`; both Ubuntu
Heimdall 2.1.0 and a local upstream-source build (commit
`3997d5cc607e6c603c6e7c0d07e42e9868c62af2`, which identifies itself as 1.4.2)
then timed out waiting for the Download Mode handshake (`-7`, zero bytes).
This is a current protocol/session-state failure, not a boot-image size or PIT
partition mismatch. The handset still enumerates as `04e8:685d` and needs the
physical key reset before another clean flash attempt.

On the later 2026-10-31 host check, the Samsung USB device was no longer
enumerated and `adb devices -l` was empty. The boot candidate was rebuilt and
validated locally; it was not sent to the phone.

On the next connection, ADB authorized the same `SM-A325F` (`A325FXXSCDXL2`,
unlocked). A direct Heimdall 2.1.0 flash attempt now initialized and began its
session successfully, proving the earlier handshake failure was cleared by a
fresh `adb reboot download` without a preceding PIT read. It then rejected
`--BOOT` because the PIT partition is lowercase `boot`; Heimdall sent a reboot
after the error, and no flash/write occurred. The known-good PIT identifies
`boot` as partition ID 36, 65,536 sectors (32 MiB). A fresh
`heimdall flash --36 ... --wait` is now waiting for the phone in Download Mode.

That wait completed after `adb reboot download`: Heimdall 2.1.0 uploaded the
candidate to partition ID 36, reported `boot upload successful`, and rebooted
the handset. This is the first confirmed write. After reboot, the phone did
not re-enumerate on USB or appear in ADB during the following 35 seconds, so
Android, UEFI and XNU boot success are all unverified. The exact stock boot
image remains available for recovery once Download Mode is reachable again.

After the handset reported a Samsung-logo boot failure, Heimdall was used to
restore the matching stock `boot.img` to PIT ID 36. It again reported
`boot upload successful` and rebooted. During the following 52 seconds the
phone remained absent from USB and ADB, so stock-boot restoration alone has
not yet restored a visible Android session. The next recovery step requires
bringing the handset back to Download Mode before considering a full firmware
restore.

The phone later reappeared in MTP/ADB mode and reported `sys.boot_completed=1`
with build `A325FXXSCDXL2`, confirming that the first stock boot restoration
returned it to Android. A loader self-test payload (`checkpoint=999`) was then
packaged and flashed to `boot`; Heimdall again reported `boot upload
successful`. The device did not re-enumerate over USB after that test. The
matching stock `boot.img` was flashed again successfully. The phone now
enumerates as Samsung MTP and ADB is authorized. The latest read reports
`sys.boot_completed=1`, build `A325FXXSCDXL2`, `flash.locked=0`, and verified
boot state `orange`; stock Android is working again. The loader self-test
screen result was not captured from the host. The A32 PIT has no `logdump`
partition, and this UEFI build has no MTK USB device transport.

## Stock boot contract

AOSP unpack_bootimg.py at commit
`3c1e9234d92949edb16c48903563f88943203df8` unpacked the boot image:

| Field | Value |
|---|---|
| Header version / page size | 2 / 2048 bytes |
| Kernel load address | 0x40080000 |
| Ramdisk load address | 0x47c80000 |
| Tags and DTB load address | 0x4bc80000 |
| Kernel | gzip, 14699914 bytes compressed |
| Ramdisk | gzip, 1979389 bytes compressed |
| DTB section | Android DT table, 99303 bytes |
| Header OS version / patch | 12.0.0 / 2025-01 |
| Command line | bootopt=64S3,32N2,64N2 loop.max_part=7 |

`uefi/files/Resources/Configs/a32.toml` records the same load addresses,
header version, page size and command line for a future UEFI image. Run
`tools/verify-boot-layout.py <stock boot.img>` to reject a mismatch before
packaging. The MT6768-family BootShim at `uefi-merlinx` commit
`49462c9374c96229848c9a11f308e33589d6ced3` compiled as a 320-byte
ARM64 image header for FD base `0x40080000` and FD size `0x300000`; its header
text offset, total size and `ARM\x64` magic were checked on the host. This
does not provide an A32 UEFI volume.

The header OS field says 12 while the running Android fingerprint says 13.
Record both as observed; do not rewrite the header based on the fingerprint.

## Device-tree selection

The DTB section contains one base tree. The DTBO table contains three entries.
Their custom words are `[0,1,0,0]`, `[2,3,0,0]`, and `[4,32,0,0]`.
Together with the r00/r02/r04 source variants and reported revision 4, this
supports selecting entry 2 for analysis. The bootloader's selection logic has
not been verified from its code. The running phone now reports
`ro.boot.dtb_idx=0` and `ro.boot.dtbo_idx=2`, confirming that these are the
selected stock entries on this boot.

libfdt `fdtoverlay` successfully applied entry 2 to the base tree, producing
`trees/a32-r04.dtb`; dtc decompiled it to `trees/a32-r04.dts`.
The future Android boot image must carry the **base** tree (`base-0.dtb`),
because LK selects and applies DTBO entry 2. Packing the already merged
`a32-r04.dtb` as the boot DTB would risk applying the overlay twice.
These are stock-file trees, not a capture of the final tree patched by LK.
In particular, the memory ranges and framebuffer address must be obtained
from the actual boot handoff before use.

| Block | Extracted facts |
|---|---|
| Root | compatible mediatek,MT6768 |
| PSCI | arm,psci-1.0; SMC method |
| Timer | arm,armv8-timer |
| GICv3 | distributor 0x0c000000/0x40000; redistributors 0x0c040000/0x200000 |
| UART0 | mediatek,mt6577-uart; 0x11002000, size 0x1000 |
| eMMC host | mediatek,msdc; 0x11230000, size 0x10000 |
| Touch | stm,stm_ts at I2C6 address 0x49; enabled |
| Panel nodes | S6E3FC3 panel node, 1080 x 2400; `/chosen` names `hx83112b_fhdp_dsi_cmd_auo_rt5081_drv` and says `islcm_inited=0` in the stock tree. The live selected panel and scanout must be measured. |

These facts do not enable the existing Qualcomm drivers on MediaTek.

The stock DTB `/memory` node contains only `0x40000000..0x7e605000`.
This is a stock-file input, not a reliable complete RAM map for the running
phone. `/chosen` also contains a framebuffer base whose bytes must not be
treated as a measured live address. Neither can be copied into a UEFI memory
map without observing LK's final handoff.

Read-only ADB measurements from the running SM-A325F show 4 KiB pages and
`MemTotal=3733032 kB`. `/proc/zoneinfo` exposes these zone spans (not a list
of safe, contiguous, unreserved UEFI allocations):

| Zone | Start | End (exclusive) | Present RAM |
|---|---:|---:|---:|
| DMA | 0x40000000 | 0x100000000 | 2885.6 MiB |
| Normal | 0x100000000 | 0x11b000000 | 432 MiB |
| Movable | 0x11b000000 | 0x13fff5000 | 592 MiB |

The actual memory map extends above 4 GiB; the stock-file `/memory` node is
therefore incomplete as a description of the live kernel's memory. ADB shell
cannot read `/proc/iomem`, `/sys/firmware/fdt`, `/memory/reg`, or the live
`/chosen` framebuffer properties on this Android build. Android's display
service reports a 1080 x 2400 internal display with 60 and 90 Hz modes; this
does not reveal the physical scanout address or the panel's UEFI init sequence.
An [MT6769T U-Boot bring-up on Redmi 9](https://github.com/hataketsu/mt6768-mainline-notes)
documents the same class of issue: LK's FDT at `x0` carries the real memory
and reserved ranges, while the static downstream tree does not. Its addresses
and reservation list are for a different phone and are not A32 values. The
A32 UEFI memory driver must parse **this phone's** FDT handoff at runtime.

The public A32 downstream tree was checked at commit
`9c91f8093f00869692e2ead2d00d09e20b9f25e8`, including its r00/r02/r04 board
trees. It confirms the panel and dynamic MediaTek heap descriptions, but does
not expose LK's final FDT map. It therefore cannot replace a live handoff
capture for memory or framebuffer addresses.

## MT6768 reference and loader probe

[uefi-merlinx](https://github.com/Dracen-W/uefi-merlinx) and its
[device record](https://github.com/Dracen-W/UniXNU-merlinx/blob/main/docs/devices/merlinx.md)
provide a source reference for another MT6768/MT6769 phone. Their BootShim,
GIC support and eMMC work show relevant implementation paths. Their fixed
UEFI stack, FD, heap, reservations, panel, and 64 MiB `p33` boot image are
Redmi Note 9-specific. A32's stock `boot.img` is 32 MiB, and its bootloader
interface has not been verified to accept merlinx's `fastboot` workflow.
The merlinx port itself reports launchd exec but no complete iOS userland.

`xnuloader` accepts an explicit `platform=a32` XNUP entry made by
`mkpayload.py --platform a32`. The profile uses the stock DTB's GICv3
addresses, PSCI SMC and one CPU. It deliberately advertises no PL011 UART.
The local UEFI image now publishes LK's initrd as Block I/O and connects the
FAT driver; its UniXNU config launches `BOOTAA64.EFI` from that volume, where
the loader reads `EFI/hakios/payload.bin`. The host candidate fits the stock
32 MiB boot partition, but neither the FAT handoff nor the UEFI/XNU boot path
has been exercised on A32 hardware.

## Remaining boot work

The A32 UEFI package compiles as a 3 MiB EDK2 firmware volume using the local
LLVM 18 toolchain and pinned `uefi-merlinx` reference source. A package script
builds a diagnostic Android boot image and rejects images over the 32 MiB
partition limit. The loader can now scan UEFI Simple File System volumes for
`\\EFI\\hakios\\system.apfs` and stream it directly into the resident RAM
disk slot; this avoids a second full-size buffer. The firmware's MT6768 MSDC
driver exposes two hosts and the A32 config enables the eMMC path. Android
mounted the inserted 29 GiB FAT32 microSD, and the APFS image and payload were
copied there with matching SHA-256 hashes.

A microSD self-test boot image was built and flashed to the A32 boot partition.
The phone showed the Samsung logo/error but no observable UniXNU loader text.
The test therefore did not confirm that UEFI started, that UEFI mounted the
microSD, or that the APFS image fit in the live memory window. The matching
stock `boot.img` was flashed back and Android was confirmed running at build
`A325FXXSCDXL2` (`sys.boot_completed=1`). The candidate fits the stock 32 MiB
partition. The live FDT, initrd filesystem connection, GOP/display handoff,
and XNU entry remain unverified; no XNU boot has been confirmed.

On 2026-10-31, a later UEFI-hold diagnostic image was flashed to boot; Heimdall
reported `boot upload successful` and rebooted the phone. The user saw the
Samsung logo and red unofficial-software warning, then reported entering
Download Mode. No UEFI banner, haptic response, or XNU output was reported, so
the test still does not locate the failure stage. The first haptic probe had a
known false-negative path: it returned without pulsing if `ldo_vibr` was
already enabled. That probe was changed to save the regulator state, force a
short enable cycle, and restore the saved state; the rebuilt image has not
provided a confirmed hardware result. The user then instructed us not to boot
or flash the phone. The stock image has not been restored after this latest
diagnostic flash, and no device commands have been issued since that
instruction. The current Download Mode state is user-reported.

An earlier analysis incorrectly said `GetMemoryMapFromFdt()` had no caller.
That was wrong: `devices/a32/uefi/patches/0001-a32-live-fdt-memory-pei.patch`
passes SEC's saved entry argument into `MemoryPeim()`, which calls the FDT
parser before enabling the MMU. The patch stages and the firmware builds. This
only establishes the host-side call path; it does not establish that the A32
bootloader passed a valid live FDT or that the parser succeeded on the phone.

The iPhone X iOS 16.5 (20F66) IPSW was obtained from Apple's update CDN in
the ignored `out/a32/ipsw/` directory. Its size is 6,165,698,198 bytes and
SHA-256 is `c1091c401f67e3aa7cdfeb2cc19e6c79be3c957aae4e097a019e9ccea07d52f2`.
`sysimage/unpack.sh` successfully extracted the root filesystem, cryptexes,
dyld shared cache and Apple device tree. `xnuloader/mkidentity.sh` produced
`identity.h` from that device tree, and `xnuloader/build.sh` linked a 71,680
byte ARM64 UEFI application. The host-only XNUP container under
`out/a32/a32-payload.bin` includes the generic kernel and small root APFS.
These artifacts do not supply the missing A32 boot handoff or hardware drivers.
`make images` also built `userland/root.apfs` and the 2.4 GiB
`userland/system.apfs` from the verified IPSW. This is a host build, not a
phone boot test. A `CHECK=1 SYSTEM=1` rebuild passed `apfsck -cw` and
independent `apfs-tool` readback against the source trees: 477 entries in
`root.apfs` and 62,262 entries in `system.apfs`.

`tools/apfs/mksparse.py trace userland/system.apfs` walked all 62,262 system
entries and found 601,853 of 604,670 APFS blocks necessary for that walk. The
resulting sparse image would be 2,467,612,664 bytes (2.47 GB), nearly the size
of the original container. Sparse packing therefore does not make this iOS
system volume fit the current resident-RAM-disk design; it needs a different
storage path or a smaller bootable system subset.

Host `zstd -3` compression produced 2,355,480,439 bytes (about 4.5% smaller).
Compression alone is not a useful capacity fix for this built APFS image; a
compressed-in-memory block path would still need to hold almost all of its
data and add decompression to every block read.

The A32 configuration and generated XNU tree pass repository configuration
checks. Host tools, the Theos cctools and iPhoneOS16.5 SDK were prepared under
`out/a32/`; stage 1 and stage 2 dependency setup completed. The generic XNU
kernel was compiled as `hakios-kernel` (14 MiB) for the A32 configuration.
`make kernel` passed through the repository's selective build judge; raw XNU
`make` still exits 2 at its kext symbol-set checks. This kernel
contains no A32-specific drivers, boot loader or iOS userland integration, so
its existence is not evidence of a bootable A32 port.
