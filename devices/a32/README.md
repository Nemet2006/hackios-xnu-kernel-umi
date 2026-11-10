# Samsung Galaxy A32 4G (SM-A325F, a32) — port scaffold

This directory records a new MediaTek port. Diagnostic Android boot images
and a loader self-test image were flashed to the Galaxy A32. A previous stock
boot restore returned the phone to Android, but the latest diagnostic image
was later flashed again. The user reports a Samsung logo and red unofficial
software warning, then Download Mode; neither UEFI nor XNU boot has been
confirmed. No stock restore has been made after that latest flash. The Xiaomi Mi 10
(UMI) port uses Qualcomm SM8250 hardware, Qualcomm UEFI protocols, Adreno
graphics, UFS storage and a QCA6390 radio. Those implementations are specific
to the Xiaomi phone.

The user's product code is `SM-A325FZKGXSG`, identifying the `SM-A325F`
model. This code is not the installed firmware build number. The installed
build was confirmed over ADB below; the full device tree and board revision
still need to be verified before assigning register addresses and pins.
The `mt6768` name follows the platform name used by available A32 Android
kernel sources; the application processor may be labelled MT6769V in hardware
teardowns. Verify the identifiers on the target device.

## What is present

- `configs/a32_defconfig` selects the common kernel and the new `mt6768`
  SoC fragment.
- `configs/a32.config` disables the existing phone-specific drivers and
  firmware loading. No A32 driver is marked as working.
- `device.conf` records unimplemented subsystems.
- `xnuloader/mkpayload.py --platform a32` selects a one-CPU loader profile
  with the stock GICv3 addresses. The candidate boot image now contains the
  A32 UEFI volume, a FAT initrd, the XNUP payload and the UEFI loader.
- `uefi/files/Resources/Configs/a32.toml` records the stock Android boot
  address contract. `tools/verify-boot-layout.py` checks it against a stock
  image before any new boot image is assembled.
- `uefi/build-local.sh` compiles an A32 EDK2 firmware volume from the pinned
  local reference sources. The SEC/PEI path parses LK's live FDT before MMU
  setup, subtracts fixed reservations and registers the handoff framebuffer.
  The firmware compiles, but has not been run on the phone. The candidate has
  not been accepted by Samsung's bootloader or shown to boot.

`tools/hakios-device.py check a32` checks configuration structure only.
Passing it is **not** evidence that the kernel boots.

With Android authorized over ADB, repeat the read-only live hardware probe:

```sh
python3 devices/a32/tools/probe-live.py --output out/a32/live-probe.json
```

It verifies the model and records selected DTB/DTBO entries, RAM zone spans
and display size. The JSON contains no serial number or full boot arguments.
Zone spans do not identify safe UEFI allocations.

## Observed on the connected phone

Read-only ADB inspection on 2026-10-30 confirmed:

| Property | Value |
|---|---|
| Model / device | `SM-A325F` / `a32` |
| Android build | `A325FXXSCDXL2` (Android 13) |
| Board platform / hardware | `mt6768` / `mt6769t` |
| Stock kernel | Linux `4.14.186-27270957`, aarch64 |
| Storage | eMMC (`mmcblk0`); `boot`, `dtbo`, `lk`, `recovery` and `vbmeta` partitions are present |
| Device tree nodes visible | `gic500@0c000000`, `msdc@11230000`, `mali@13040000`, `s6e3fc3`, `touch` |
| Boot tree selection | `ro.boot.dtb_idx=0`, `ro.boot.dtbo_idx=2` (confirmed on a later ADB session) |
| Live display | 1080 x 2400; 60/90 Hz modes |

The ADB shell is unprivileged and no `su` executable is present. Reading
`/sys/firmware/fdt`, `/proc/cmdline` and even device-tree property contents
returns `Permission denied`. Directory names alone do not establish register
sizes, interrupt numbers, display timings or a usable boot handoff. Obtain a
matching stock firmware package for `A325FXXSCDXL2` to extract its boot and
device-tree images, or use another authorized read-only source for those files.

The matching XSG firmware was downloaded from Samsung FUS and its boot,
recovery and DTBO images extracted locally. See [BOOT-INVESTIGATION.md](BOOT-INVESTIGATION.md)
for hashes, boot header fields, overlay selection, the successful diagnostic
flash, stock boot restoration and remaining limitations. A public [SM-A325F Linux kernel tree](https://github.com/realahnet/android_kernel_samsung_a32)
is available as hardware reference, though its branch is based on a different
stock build and requires comparison with this phone's images.

## Required device data

The stock files and a composed revision-4 tree now exist under
`out/a32/stock/`. To repeat extraction (requires the Python `lz4` package):

```sh
python3 devices/a32/tools/extract-stock.py out/a32/stock/SM-A325F_3_20241230123541_brfp5arl3v_fac.zip out/a32/stock/extracted
```

The live bootloader-patched device tree is still unavailable.

With Android running and USB debugging enabled, collect the following from
the actual phone. These commands are read-only. Keep firmware and full device
images private; do not commit them to this repository.

```sh
adb devices -l
adb shell getprop ro.product.model
adb shell getprop ro.product.device
adb shell getprop ro.build.version.incremental
adb shell getprop ro.build.fingerprint
adb shell uname -a
adb shell cat /proc/cmdline
adb pull /sys/firmware/fdt /tmp/a32-device-tree.dtb
```

On this phone `/sys/firmware/fdt` is inaccessible to ADB shell. Obtain the
DTB/DTBO from **this phone's matching stock firmware**. An unlocked bootloader alone does not
provide a UEFI environment or make the Qualcomm RAM-boot runner work on Samsung.

## Bring-up work

1. Verify the exact SM-A325 variant, stock firmware revision, DTB, partition
   layout, boot mode, framebuffer and serial or USB logging path.
2. Run a reversible A32 UEFI boot test and verify the live FDT, memory map,
   initrd FAT handoff, framebuffer, and XNU entry state.
3. Bring up interrupts, timers, memory and one CPU before enabling SMP.
4. Add A32-specific eMMC, display, input, power, thermal, Mali, audio and radio
   drivers one at a time, checking each against the device tree and stock
   kernel source. Keep all unsupported drivers disabled.
5. Validate a reversible boot on the target phone before any persistent image
   or flashing workflow is considered.

The A32 Android kernel source is useful as hardware documentation and for
extracting device-specific constants. It is Linux source; it does not itself
make XNU compatible with the phone.

The current stock Android boot remains installed. A microSD boot candidate was
tested and showed only the Samsung logo/error; no UEFI loader or XNU output was
confirmed. The stock boot image was restored and Android boot was verified.
The loader source now includes a microSD APFS read path, but that path has not
been reached on-device. The current payload contains only the small boot/root
APFS image. The full
iOS 16.5 system APFS is 2.47 GB, and tracing its file tree still requires
601,853 of 604,670 container blocks. It does not fit the current resident
RAM-disk layout as a sparse image. Full iOS userland therefore still needs a
working storage path and integration in XNU; the generic kernel build and
boot-image package are not an iOS installation.
