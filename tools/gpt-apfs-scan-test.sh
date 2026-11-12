#!/bin/sh
# Host test for the production read-only GPT/APFS scanner.
set -eu
cd "$(dirname "$0")/.."
grep -qx 'standard bsd/dev/hakios.gpt_apfs.c' drivers/storage/conf
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
${CC:-cc} -std=c11 -O1 -g -Wall -Wextra -Werror \
  -fsanitize=address,undefined -fno-sanitize-recover=all \
  -Ixnu/files/bsd \
  tools/gpt-apfs-scan-test.c drivers/storage/hakios.gpt_apfs.c \
  drivers/storage/hakios.readonly_block.c drivers/storage/hakios.readonly_scan.c \
  -o "$tmp/gpt-apfs-scan-test"
"$tmp/gpt-apfs-scan-test"
