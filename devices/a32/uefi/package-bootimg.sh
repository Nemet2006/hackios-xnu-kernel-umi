#!/bin/sh
# Build a host-verified Android boot image candidate. This script never flashes.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
OUT="$ROOT/out/a32"
UEFI="$OUT/reference-uefi-merlinx"
UNIXNU="$OUT/reference-unixnu-merlinx"
FD="$UEFI/Build/a32Pkg/DEBUG_CLANGPDB/FV/SILICIUM_UEFI.fd"
DTB="$OUT/stock/trees/base-0.dtb"
PAYLOAD=${PAYLOAD:-"$OUT/a32-payload.bin"}
LOADER="$ROOT/xnuloader/loader-a32.efi"
RAMDISK="$OUT/a32-ramdisk-24m.img"
IMAGE=${IMAGE:-"$OUT/boot-a32-diagnostic.img"}
STOCK="$OUT/stock/extracted/boot.img"
CAPACITY=$((32 * 1024 * 1024))

for tool in mkfs.vfat mmd mcopy mdir python3 cmp mktemp; do
  command -v "$tool" >/dev/null 2>&1 || { echo "Missing required tool: $tool" >&2; exit 1; }
done
for file in "$FD" "$DTB" "$PAYLOAD" "$STOCK" "$UNIXNU/unixnu"; do
  [ -f "$file" ] || { echo "Missing build input: $file" >&2; exit 1; }
done

if [ -n "${EXPECTED_CHECKPOINT:-}" ]; then
  python3 "$ROOT/devices/a32/tools/verify-payload.py" "$PAYLOAD" --checkpoint "$EXPECTED_CHECKPOINT"
else
  python3 "$ROOT/devices/a32/tools/verify-payload.py" "$PAYLOAD"
fi

PATH="$OUT/host-root/usr/lib/llvm-18/bin:/usr/lib/llvm-18/bin:$PATH" \
  "$ROOT/xnuloader/build.sh" --a32

python3 "$ROOT/devices/a32/tools/verify-boot-layout.py" \
  --config "$ROOT/devices/a32/uefi/files/Resources/Configs/a32.toml" "$STOCK"

rm -f "$RAMDISK"
mkfs.vfat -F 16 -C "$RAMDISK" 24576 >/dev/null
mmd -i "$RAMDISK" ::/EFI
mmd -i "$RAMDISK" ::/EFI/BOOT
mmd -i "$RAMDISK" ::/EFI/UniXNU
mmd -i "$RAMDISK" ::/EFI/hakios
mcopy -i "$RAMDISK" "$LOADER" ::/EFI/BOOT/BOOTAA64.EFI
mcopy -i "$RAMDISK" "$ROOT/devices/a32/uefi/unixnu.toml" ::/EFI/UniXNU/unixnu.toml
mcopy -i "$RAMDISK" "$PAYLOAD" ::/EFI/hakios/payload.bin
mdir -i "$RAMDISK" ::/EFI/BOOT/BOOTAA64.EFI >/dev/null
mdir -i "$RAMDISK" ::/EFI/UniXNU/unixnu.toml >/dev/null
mdir -i "$RAMDISK" ::/EFI/hakios/payload.bin >/dev/null
TMP=$(mktemp -d "$OUT/package-check.XXXXXX")
trap 'rm -rf "$TMP"' EXIT HUP INT TERM
mcopy -i "$RAMDISK" ::/EFI/BOOT/BOOTAA64.EFI "$TMP/loader.efi"
mcopy -i "$RAMDISK" ::/EFI/hakios/payload.bin "$TMP/payload.bin"
cmp "$LOADER" "$TMP/loader.efi"
cmp "$PAYLOAD" "$TMP/payload.bin"

PATH="/usr/lib/llvm-18/bin:$PATH" "$UNIXNU/unixnu" bootimg \
  -D "$ROOT/devices/a32/uefi" --out "$OUT/unixnu-a32" \
  --uefi "$UEFI" --fd "$FD" --dtb "$DTB" --ramdisk "$RAMDISK" \
  -o "$IMAGE"

python3 - "$IMAGE" "$CAPACITY" <<'PY'
from pathlib import Path
import sys

image = Path(sys.argv[1])
capacity = int(sys.argv[2])
size = image.stat().st_size
if size > capacity:
    raise SystemExit(f"boot image is {size} bytes; partition capacity is {capacity}")
print(f"boot image fits: {size}/{capacity} bytes")
PY
