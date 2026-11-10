#!/usr/bin/env python3
"""Compare A32 UEFI boot-image settings with an exact stock boot.img header."""

import argparse
from pathlib import Path
import struct
import tomllib


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stock_boot", type=Path)
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[1] /
                        "uefi/files/Resources/Configs/a32.toml")
    args = parser.parse_args()
    with args.config.open("rb") as stream:
        config = tomllib.load(stream)
    with args.stock_boot.open("rb") as stream:
        header = stream.read(2048)
    if header[:8] != b"ANDROID!":
        raise ValueError("stock image has no Android boot magic")
    values = struct.unpack_from("<10I", header, 8)
    _, kernel_addr, _, ramdisk_addr, second_size, _, tags_addr, page_size, version, _ = values
    dtb_size = struct.unpack_from("<I", header, 1648)[0]
    dtb_addr = struct.unpack_from("<Q", header, 1652)[0]
    image = config["boot_image"]
    base = image["base"]
    expected = {
        "kernel address": (kernel_addr, base + image["kernel_offset"]),
        "ramdisk address": (ramdisk_addr, base + image["ramdisk_offset"]),
        "tags address": (tags_addr, base + image["tags_offset"]),
        "DTB address": (dtb_addr, base + image["dtb_offset"]),
        "page size": (page_size, image["pagesize"]),
        "header version": (version, image["header_version"]),
    }
    failed = [name for name, (stock, planned) in expected.items() if stock != planned]
    for name, (stock, planned) in expected.items():
        print(f"{name}: stock={stock:#x} planned={planned:#x}")
    if second_size or not dtb_size:
        failed.append("unexpected second stage or missing DTB")
    if config["uefi_fd"]["base"] != kernel_addr:
        failed.append("FD base differs from kernel load address")
    # The matching firmware's A32_EUR_OPEN.pit gives boot 65536 x 512-byte
    # sectors. The stock image is padded to this exact 32 MiB capacity.
    if args.stock_boot.stat().st_size != 32 * 1024 * 1024:
        failed.append("stock boot image is not the expected 32 MiB")
    if failed:
        raise ValueError("boot contract mismatch: " + ", ".join(failed))
    print("A32 stock boot address and header contract matches")


if __name__ == "__main__":
    main()
