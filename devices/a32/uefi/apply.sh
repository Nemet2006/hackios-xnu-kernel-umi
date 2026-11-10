#!/bin/sh
# Stage the A32 UEFI package and SEC/PEI patch into the pinned source checkout.
# It does not build a boot image or touch the phone.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
HERE="$ROOT/devices/a32/uefi"
SOURCE=${UEFI_SOURCE:-"$ROOT/out/a32/reference-uefi-merlinx"}
EXPECTED=$(cat "$HERE/BASE")
ACTUAL=$(git -C "$SOURCE" rev-parse HEAD)
if [ "$ACTUAL" != "$EXPECTED" ]; then
  echo "A32 UEFI base mismatch: expected $EXPECTED, got $ACTUAL" >&2
  exit 1
fi
mkdir -p "$SOURCE/Platforms/Samsung" "$SOURCE/Resources/Configs"
for PATCH in "$HERE"/patches/*.patch; do
  if git -C "$SOURCE" apply --check "$PATCH" >/dev/null 2>&1; then
    git -C "$SOURCE" apply "$PATCH"
  elif ! git -C "$SOURCE" apply --reverse --check "$PATCH" >/dev/null 2>&1; then
    echo "A32 UEFI patch $PATCH does not apply cleanly to $EXPECTED" >&2
    exit 1
  fi
done
cp -a "$HERE/files/Platforms/Samsung/a32Pkg" "$SOURCE/Platforms/Samsung/"
cp "$HERE/files/Resources/Configs/a32.toml" "$SOURCE/Resources/Configs/a32.toml"
echo "A32 UEFI source staged in $SOURCE"
