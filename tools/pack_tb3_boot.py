#!/usr/bin/env python3
"""Replace only the kernel in a Lenovo TB3-710F Android boot image.

This creates an output file; it never talks to ADB, fastboot, SP Flash Tool,
or a block device.  It currently accepts legacy Android boot header v0 only.
"""

import argparse
import struct
import sys
from pathlib import Path


MAGIC = b"ANDROID!"
PAGE_SIZE_OFF = 36
HEADER_V0_SIZE = 1632
ZIMAGE_MAGIC_OFF = 0x24
ZIMAGE_MAGIC = 0x016F2818


def u32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def align(value: int, size: int) -> int:
    return (value + size - 1) & ~(size - 1)


def pack(original: bytes, kernel: bytes) -> bytes:
    if len(original) < HEADER_V0_SIZE or original[:8] != MAGIC:
        raise ValueError("input does not look like an Android boot image")
    if len(kernel) <= ZIMAGE_MAGIC_OFF + 4:
        raise ValueError("loader kernel is too small to contain a zImage header")
    if u32(kernel, ZIMAGE_MAGIC_OFF) != ZIMAGE_MAGIC:
        raise ValueError("loader is missing the Linux zImage magic at offset 0x24")

    page = u32(original, PAGE_SIZE_OFF)
    if page < HEADER_V0_SIZE or page & (page - 1):
        raise ValueError(f"unsupported boot page size: {page}")

    ksize, rsize = u32(original, 8), u32(original, 16)
    ssize, dsize = u32(original, 24), u32(original, 40)
    if u32(original, 44) != 0:
        raise ValueError("nonzero legacy header field at offset 44; refusing unknown format")

    old_koff = page
    old_roff = old_koff + align(ksize, page)
    old_soff = old_roff + align(rsize, page)
    old_doff = old_soff + align(ssize, page)
    old_end = old_doff + align(dsize, page)
    if old_end > len(original):
        raise ValueError("component sizes in boot header exceed the input image")

    ramdisk = original[old_roff:old_roff + rsize]
    second = original[old_soff:old_soff + ssize]
    dt = original[old_doff:old_doff + dsize]

    out = bytearray(original[:page])
    struct.pack_into("<I", out, 8, len(kernel))
    out.extend(kernel)
    out.extend(bytes(align(len(kernel), page) - len(kernel)))
    out.extend(ramdisk)
    out.extend(bytes(align(rsize, page) - rsize))
    out.extend(second)
    out.extend(bytes(align(ssize, page) - ssize))
    out.extend(dt)
    out.extend(bytes(align(dsize, page) - dsize))

    if len(out) > len(original):
        raise ValueError(
            f"repacked image ({len(out)} bytes) exceeds source partition size "
            f"({len(original)} bytes)"
        )
    out.extend(bytes(len(original) - len(out)))
    return bytes(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original_boot", type=Path, help="read-only backup of current boot partition")
    parser.add_argument("loader_zimage", type=Path, help="built uniLoader zImage")
    parser.add_argument("output_boot", type=Path, help="new image file to create")
    args = parser.parse_args()

    try:
        original = args.original_boot.read_bytes()
        kernel = args.loader_zimage.read_bytes()
        result = pack(original, kernel)
        args.output_boot.write_bytes(result)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"Wrote {args.output_boot} ({len(result)} bytes)")
    print("Original ramdisk, boot arguments, load addresses, and partition size were retained.")
    print("This only creates a file; it does not flash the tablet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

