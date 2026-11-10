#!/usr/bin/env python3
"""Read-only ADB probe for the SM-A325F boot contract; writes no phone data."""

import argparse
import json
import re
import subprocess
import sys


def adb(*args):
    result = subprocess.run(["adb", *args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", help="ADB serial if more than one device is connected")
    parser.add_argument("--output", help="write JSON report here; defaults to stdout")
    args = parser.parse_args()
    prefix = ("-s", args.serial) if args.serial else ()
    state = adb(*prefix, "get-state")
    if state != "device":
        raise RuntimeError(f"ADB state is {state!r}; authorize USB debugging on the phone")

    names = {
        "manufacturer": "ro.product.manufacturer",
        "model": "ro.product.model",
        "device": "ro.product.device",
        "build": "ro.build.version.incremental",
        "platform": "ro.board.platform",
        "hardware": "ro.boot.hardware",
        "revision": "ro.boot.revision",
        "dtb_index": "ro.boot.dtb_idx",
        "dtbo_index": "ro.boot.dtbo_idx",
        "verified_boot": "ro.boot.verifiedbootstate",
        "flash_locked": "ro.boot.flash.locked",
    }
    facts = {name: adb(*prefix, "shell", "getprop", prop) for name, prop in names.items()}
    if facts["manufacturer"].lower() != "samsung" or facts["model"] != "SM-A325F":
        raise RuntimeError("connected device is not a Samsung SM-A325F")

    meminfo = adb(*prefix, "shell", "cat", "/proc/meminfo")
    match = re.search(r"^MemTotal:\s+(\d+) kB$", meminfo, re.MULTILINE)
    if not match:
        raise RuntimeError("could not read MemTotal")
    facts["mem_total_kib"] = int(match.group(1))
    facts["page_size"] = int(adb(*prefix, "shell", "getconf", "PAGESIZE"))
    facts["display_size"] = adb(*prefix, "shell", "wm", "size")

    zoneinfo = adb(*prefix, "shell", "cat", "/proc/zoneinfo")
    zones = []
    for block in re.split(r"(?=^Node \d+, zone\s+)", zoneinfo, flags=re.MULTILINE):
        head = re.search(r"^Node \d+, zone\s+(\w+)", block)
        if not head:
            continue
        values = {}
        for field, pattern in {
            "start_pfn": r"^\s*start_pfn:\s+(\d+)",
            "spanned_pages": r"^\s*spanned\s+(\d+)",
            "present_pages": r"^\s*present\s+(\d+)",
        }.items():
            found = re.search(pattern, block, re.MULTILINE)
            if found:
                values[field] = int(found.group(1))
        if len(values) == 3:
            zones.append({
                "name": head.group(1),
                "start": f"0x{values['start_pfn'] * facts['page_size']:x}",
                "end_exclusive": f"0x{(values['start_pfn'] + values['spanned_pages']) * facts['page_size']:x}",
                "present_pages": values["present_pages"],
            })
    if not zones:
        raise RuntimeError("could not parse /proc/zoneinfo")
    facts["zones"] = zones
    facts["note"] = "zone spans are not a UEFI free-memory or reserved-memory map"
    encoded = json.dumps(facts, indent=2) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(encoded)
    else:
        sys.stdout.write(encoded)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as exc:
        raise SystemExit(f"probe-live: {exc}") from exc
