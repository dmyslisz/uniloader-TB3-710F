#!/usr/bin/env python3
"""Gzip a raw HFS+ volume for the Lenovo TB3-710F XNU memory disk.

Input must be a decrypted, raw HFS+ volume image beginning at the volume's
first byte. This tool does not extract or decrypt Apple firmware, create an
HFS+ filesystem, or communicate with a device.
"""

import argparse
import gzip
import hashlib
import os
import shutil
import struct
import sys
import tempfile
from pathlib import Path


DEFAULT_RAMDISK_PA = 0x90000000
DEFAULT_RAM_END = 0xBED00000
PAGE_SIZE = 0x1000


def inspect_volume(path: Path, ramdisk_pa: int, ram_end: int) -> tuple[int, int, str]:
    size = path.stat().st_size
    if size < 1536:
        raise ValueError("input is too small to contain an HFS+ volume header")
    with path.open("rb") as source:
        source.seek(1024)
        header = source.read(48)
    signature, version = struct.unpack_from(">HH", header, 0)
    if (signature, version) not in ((0x482B, 4), (0x4858, 5)):
        raise ValueError("no HFS+ (H+) or HFSX (HX) volume header at offset 1024")
    block_size, total_blocks = struct.unpack_from(">II", header, 40)
    if block_size < 512 or block_size > 65536 or block_size & (block_size - 1):
        raise ValueError(f"invalid HFS+ block size: {block_size}")
    if not total_blocks or total_blocks * block_size > size:
        raise ValueError("HFS+ volume block count exceeds the input image size")
    if ramdisk_pa < 0x80000000 or ram_end <= ramdisk_pa:
        raise ValueError("invalid physical RAM range")
    capacity = ram_end - ramdisk_pa
    rounded_size = (size + PAGE_SIZE - 1) & ~(PAGE_SIZE - 1)
    if rounded_size > capacity:
        raise ValueError(
            f"raw volume ({size} bytes; page-rounded {rounded_size}) exceeds "
            f"the configured RAM-disk capacity ({capacity} bytes)"
        )
    return size, block_size, "H+" if signature == 0x482B else "HX"


def pack(source_path: Path, output_path: Path, ramdisk_pa: int, ram_end: int) -> None:
    source = source_path.resolve(strict=True)
    output = output_path.resolve(strict=False)
    if source == output:
        raise ValueError("input and output paths must be different")
    size, block_size, signature = inspect_volume(source, ramdisk_pa, ram_end)
    output.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=output.parent, prefix=output.name + ".", suffix=".tmp",
            delete=False
        ) as temporary:
            temp_name = temporary.name
            with source.open("rb") as raw:
                with gzip.GzipFile(
                    filename="", fileobj=temporary, mode="wb", compresslevel=9, mtime=0
                ) as compressed:
                    while True:
                        chunk = raw.read(1024 * 1024)
                        if not chunk:
                            break
                        digest.update(chunk)
                        compressed.write(chunk)
        os.replace(temp_name, output)
    except Exception:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
        raise
    compressed_size = output.stat().st_size
    print(f"Volume: {signature}, {size} bytes, HFS+ block size {block_size}")
    print(f"RAM-disk range: 0x{ramdisk_pa:08x}-0x{ram_end:08x} ({ram_end - ramdisk_pa} bytes)")
    print(f"Wrote gzip image: {output} ({compressed_size} bytes)")
    print(f"Uncompressed SHA-256: {digest.hexdigest()}")
    print("This only creates a file; it does not install or flash anything.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("hfs_volume", type=Path, help="decrypted raw HFS+ volume image")
    parser.add_argument("output_gz", type=Path, help="gzip image to create")
    parser.add_argument(
        "--ramdisk-pa", type=lambda x: int(x, 0), default=DEFAULT_RAMDISK_PA,
        help="physical address from CONFIG_XNU_RAMDISK_PA (default: 0x90000000)"
    )
    parser.add_argument(
        "--ram-end", type=lambda x: int(x, 0), default=DEFAULT_RAM_END,
        help="exclusive end of usable RAM (default: 0xBED00000)"
    )
    args = parser.parse_args()
    try:
        pack(args.hfs_volume, args.output_gz, args.ramdisk_pa, args.ram_end)
    except (OSError, ValueError, struct.error, EOFError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
