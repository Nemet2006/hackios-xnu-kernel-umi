#!/bin/sh
# Host test for the transport-independent read-only block core.
set -eu
cd "$(dirname "$0")/.."
grep -qx 'standard bsd/dev/hakios.readonly_block.c' drivers/storage/conf
grep -qx 'storage  bsd/dev/hakios.readonly_block.c' drivers/map
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
${CC:-cc} -std=c11 -O1 -g -Wall -Wextra -Werror \
  -fsanitize=address,undefined -fno-sanitize-recover=all \
  -Ixnu/files/bsd \
  tools/readonly-block-test.c drivers/storage/hakios.readonly_block.c \
  -o "$tmp/readonly-block-test"
"$tmp/readonly-block-test"
