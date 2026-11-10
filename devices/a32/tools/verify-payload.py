#!/usr/bin/env python3
"""Validate A32 XNUP input without touching a device or changing the payload."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

LIMIT = 63 * 1024 * 1024
# Match the bounded name table in the runtime volume validator; exclude terminator.
MAX_ENTRIES = 128
TEXT = {"platform", "cmdline", "physbase", "rdres", "kernel.ver", "checkpoint", "usb"}


def inspect(data, expected_checkpoint=None):
    if not 8 <= len(data) <= LIMIT:
        raise ValueError("payload length must be between 8 bytes and 63 MiB")
    magic, size = struct.unpack_from("<II", data)
    if magic != 0x50554E58 or size != len(data) - 8:
        raise ValueError("invalid XNUP magic or declared length")
    pos, entries, texts = 8, {}, {}
    ended = False
    while pos < len(data):
        if len(data) - pos < 24:
            raise ValueError("truncated entry header")
        raw, size, reserved = struct.unpack_from("<16sII", data, pos)
        pos += 24
        if raw == bytes(16):
            if size or reserved or pos != len(data):
                raise ValueError("invalid terminator or trailing bytes")
            ended = True
            break
        if b"\0" not in raw:
            raise ValueError("entry name is not terminated")
        name_bytes, tail = raw.split(b"\0", 1)
        if any(tail) or reserved:
            raise ValueError("nonzero reserved entry bytes")
        name = name_bytes.decode("ascii")
        if name in entries:
            raise ValueError("duplicate entry: " + name)
        if len(entries) >= MAX_ENTRIES:
            raise ValueError("too many payload entries (maximum 128)")
        padded = (size + 15) & ~15
        if padded > len(data) - pos:
            raise ValueError("entry exceeds payload: " + name)
        value = data[pos:pos + size]
        if any(data[pos + size:pos + padded]):
            raise ValueError("nonzero padding: " + name)
        entries[name] = size
        if name in TEXT:
            if not value or value[-1] != 0 or b"\0" in value[:-1]:
                raise ValueError("invalid text termination: " + name)
            texts[name] = value[:-1].decode("utf-8")
        pos += padded
    if not ended:
        raise ValueError("missing terminator")
    if texts.get("platform") != "a32":
        raise ValueError("platform must be a32")
    if not entries.get("kernel"):
        raise ValueError("missing or empty kernel")
    checkpoint = texts.get("checkpoint", "0")
    if not checkpoint.isascii() or not checkpoint.isdecimal():
        raise ValueError("checkpoint must be a decimal integer")
    checkpoint = int(checkpoint)
    if expected_checkpoint is not None and checkpoint != expected_checkpoint:
        raise ValueError(f"checkpoint {checkpoint} does not match expected {expected_checkpoint}")
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "platform": "a32", "checkpoint": checkpoint, "entries": entries,
            "mode": {998: "diagnostic-hold", 999: "loader-selftest"}.get(checkpoint, "kernel-path")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    parser.add_argument("--checkpoint", type=int, help="require this exact checkpoint (0 means absent/default)")
    args = parser.parse_args()
    try:
        with args.payload.open("rb") as source:
            data = source.read(LIMIT + 1)
        print(json.dumps(inspect(data, args.checkpoint), indent=2))
    except (OSError, ValueError) as error:
        parser.exit(1, f"payload rejected: {error}\n")


if __name__ == "__main__":
    main()
