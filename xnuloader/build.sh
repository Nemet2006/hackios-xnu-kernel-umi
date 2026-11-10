#!/bin/bash
# Build the XNU loader as a freestanding AArch64 UEFI application.
set -e
cd "$(dirname "$0")"
# the iPhone's identity for XNU, from the device tree of the builder's own IPSW (not in the repository)
[ -f identity.h ] || ./mkidentity.sh

flags=()
output=loader
case "${1:-}" in
  "") ;;
  --a32) flags+=(-DA32_VOLUME_FIRST=1); output=loader-a32 ;;
  *) echo "usage: $0 [--a32]" >&2; exit 2 ;;
esac

clang --target=aarch64-unknown-windows -ffreestanding -fno-builtin -fno-stack-protector -fshort-wchar \
  -mgeneral-regs-only -O1 -Wall -Wextra -Wno-unused-parameter "${flags[@]}" -c loader.c -o "$output.obj"
# /base: UEFI loads an image at its preferred address when that is free. The PE default (0x140000000)
# is in the middle of the phone's largest block of RAM, which XNU needs in one piece.
lld-link /subsystem:efi_application /entry:efi_main /nodefaultlib /base:0xA1000000 "/out:$output.efi" "$output.obj"
ls -la "$output.efi"
