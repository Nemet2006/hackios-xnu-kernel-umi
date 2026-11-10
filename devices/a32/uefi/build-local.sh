#!/bin/sh
# Compile the A32 EDK2 firmware volume using the pinned local UniXNU feeds.
# This is a host-only compile check. It never packages or flashes a boot image.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
UEFI="$ROOT/out/a32/reference-uefi-merlinx"
UNIXNU="$ROOT/out/a32/reference-unixnu-merlinx"
BASE="$UNIXNU/out/feeds/mu_basecore-89034cbb"
TREE="$UNIXNU/out/merlinx/tree"

for path in "$BASE/BaseTools/BinWrappers/PosixLike/build" "$UNIXNU/out/merlinx/edk2-conf/target.txt" "$UNIXNU/out/merlinx/toolchain/clang"; do
  if [ ! -e "$path" ]; then
    echo "Missing local UEFI build dependency: $path" >&2
    exit 1
  fi
done

"$ROOT/devices/a32/uefi/apply.sh"
export WORKSPACE="$UEFI"
export EDK_TOOLS_PATH="$BASE/BaseTools"
export CONF_PATH="$UNIXNU/out/merlinx/edk2-conf"
export PACKAGES_PATH="$UEFI:$UEFI/Platforms/Samsung:$UEFI/Silicon/MediaTek:$UEFI/Silicon/Silicium:$TREE/package:$TREE/drivers/DarwinBoot:$BASE:$UEFI/Common/Mu:$UEFI/Common/Mu_OEM_Sample"
export PATH="$UNIXNU/out/merlinx/toolchain:$ROOT/out/a32/host-root/usr/lib/llvm-18/bin:/usr/lib/llvm-18/bin:$BASE/BaseTools/BinWrappers/PosixLike:$BASE/BaseTools/Source/C/bin:$ROOT/out/a32/host-root/usr/bin:$ROOT/out/a32/uefi-venv/bin:$PATH"
build -p Platforms/Samsung/a32Pkg/a32.dsc -a AARCH64 -b DEBUG -t CLANGPDB -n "${JOBS:-8}" \
  -D FD_BASE=0x40080000 -D FD_SIZE=0x300000 -D FD_BLOCKS=768 \
  -D ENABLE_SECUREBOOT=0 -D DEVICE_MODEL=a32 -D MEMORY_PROTECTION=TRUE \
  -D SHIP_MODE=FALSE -D BUILDID_STRING=a32-research
