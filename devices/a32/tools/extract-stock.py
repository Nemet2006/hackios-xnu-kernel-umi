#!/usr/bin/env python3
"""Extract only A32 boot images from a matching Samsung firmware ZIP.

This reads the ZIP/AP TAR and writes files on the host. It never talks to or
writes to the phone. Install the Python lz4 package in the invoking environment.
"""

import argparse
import hashlib
import os
from pathlib import Path
import tarfile
import zipfile

try:
    import lz4.frame
except ImportError as exc:
    raise SystemExit("install the Python lz4 package: python3 -m pip install lz4") from exc


BUILD = "A325FXXSCDXL2"
IMAGES = {"boot.img.lz4", "dtbo.img.lz4", "recovery.img.lz4"}
CHUNK = 1024 * 1024


def extract_member(source, destination):
    decoder = lz4.frame.LZ4FrameDecompressor()
    digest = hashlib.sha256()
    temporary = destination.with_name(destination.name + ".partial")
    try:
        with temporary.open("wb") as output:
            while block := source.read(CHUNK):
                decoded = decoder.decompress(block)
                if decoded:
                    output.write(decoded)
                    digest.update(decoded)
            if not decoder.eof:
                raise ValueError(f"incomplete LZ4 frame: {destination.name}")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"{destination.name}: {destination.stat().st_size} bytes, sha256 {digest.hexdigest()}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("firmware_zip", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(args.firmware_zip) as archive:
        ap = [name for name in archive.namelist()
              if Path(name).name.startswith(f"AP_{BUILD}_") and name.endswith(".tar.md5")]
        if len(ap) != 1:
            raise SystemExit(f"expected one AP_{BUILD}_*.tar.md5 in firmware ZIP, found {len(ap)}")
        print(f"AP archive: {ap[0]}")
        found = set()
        with archive.open(ap[0]) as stream, tarfile.open(fileobj=stream, mode="r|") as tar:
            for member in tar:
                name = Path(member.name).name
                if not member.isfile() or name not in IMAGES:
                    continue
                if name in found:
                    raise ValueError(f"duplicate AP member: {name}")
                fileobj = tar.extractfile(member)
                if fileobj is None:
                    raise ValueError(f"cannot read AP member: {name}")
                extract_member(fileobj, args.output_dir / name.removesuffix(".lz4"))
                found.add(name)
        if "boot.img.lz4" not in found or "dtbo.img.lz4" not in found:
            raise SystemExit(f"boot or dtbo missing; found: {', '.join(sorted(found))}")


if __name__ == "__main__":
    main()
