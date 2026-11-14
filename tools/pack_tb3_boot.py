#!/usr/bin/env python3
"""Replace the kernel in a Lenovo TB3-710F legacy Android boot image.

The device's MediaTek LK expects a 512-byte MTK KERNEL wrapper before the
Linux zImage. This creates a file only; it never accesses a device.
"""

import argparse
import struct
import sys
from pathlib import Path


ANDROID_MAGIC = b"ANDROID!"
ANDROID_PAGE_SIZE_OFF = 36
ANDROID_HEADER_V0_SIZE = 1632
MTK_KERNEL_MAGIC = b"\x88\x16\x88\x58"
MTK_KERNEL_HEADER_SIZE = 0x200
MTK_KERNEL_SIZE_OFF = 4
MTK_KERNEL_NAME = b"KERNEL\0\0"
ZIMAGE_MAGIC_OFF = 0x24
ZIMAGE_MAGIC = 0x016F2818


def u32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def align(value: int, size: int) -> int:
    return (value + size - 1) & ~(size - 1)


def pack(original: bytes, zimage: bytes) -> bytes:
    if len(original) < ANDROID_HEADER_V0_SIZE or original[:8] != ANDROID_MAGIC:
        raise ValueError("input does not look like an Android boot image")
    if len(zimage) <= ZIMAGE_MAGIC_OFF + 4:
        raise ValueError("loader zImage is too small to contain its header")
    if u32(zimage, ZIMAGE_MAGIC_OFF) != ZIMAGE_MAGIC:
        raise ValueError("loader is missing Linux zImage magic at offset 0x24")

    page = u32(original, ANDROID_PAGE_SIZE_OFF)
    if page < ANDROID_HEADER_V0_SIZE or page & (page - 1):
        raise ValueError(f"unsupported Android boot page size: {page}")
    if u32(original, 44) != 0:
        raise ValueError("nonzero legacy boot header field at offset 44; refusing unknown format")

    old_kernel_size = u32(original, 8)
    ramdisk_size = u32(original, 16)
    second_size = u32(original, 24)
    dt_size = u32(original, 40)
    kernel_off = page
    if old_kernel_size < MTK_KERNEL_HEADER_SIZE:
        raise ValueError("kernel component is smaller than the MTK header")
    if kernel_off + MTK_KERNEL_HEADER_SIZE > len(original):
        raise ValueError("MTK kernel header lies outside the boot image")

    mtk_header = bytearray(original[kernel_off:kernel_off + MTK_KERNEL_HEADER_SIZE])
    if mtk_header[:4] != MTK_KERNEL_MAGIC:
        raise ValueError("TB3-710F boot image lacks the expected MTK KERNEL wrapper")
    if mtk_header[8:16] != MTK_KERNEL_NAME:
        raise ValueError("MTK kernel wrapper name is not KERNEL")
    if u32(mtk_header, MTK_KERNEL_SIZE_OFF) != old_kernel_size - MTK_KERNEL_HEADER_SIZE:
        raise ValueError("MTK inner kernel size does not match Android header")

    ramdisk_off = kernel_off + align(old_kernel_size, page)
    second_off = ramdisk_off + align(ramdisk_size, page)
    dt_off = second_off + align(second_size, page)
    end_off = dt_off + align(dt_size, page)
    if end_off > len(original):
        raise ValueError("component sizes in boot header exceed the input image")

    ramdisk = original[ramdisk_off:ramdisk_off + ramdisk_size]
    second = original[second_off:second_off + second_size]
    dt = original[dt_off:dt_off + dt_size]

    mtk_header[MTK_KERNEL_SIZE_OFF:MTK_KERNEL_SIZE_OFF + 4] = struct.pack("<I", len(zimage))
    kernel = bytes(mtk_header) + zimage
    out = bytearray(original[:page])
    struct.pack_into("<I", out, 8, len(kernel))
    out.extend(kernel)
    out.extend(bytes(align(len(kernel), page) - len(kernel)))
    out.extend(ramdisk)
    out.extend(bytes(align(ramdisk_size, page) - ramdisk_size))
    out.extend(second)
    out.extend(bytes(align(second_size, page) - second_size))
    out.extend(dt)
    out.extend(bytes(align(dt_size, page) - dt_size))

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
    parser.add_argument("loader_zimage", type=Path, help="built uniLoader Linux zImage")
    parser.add_argument("output_boot", type=Path, help="new image file to create")
    args = parser.parse_args()

    try:
        original = args.original_boot.read_bytes()
        zimage = args.loader_zimage.read_bytes()
        result = pack(original, zimage)
        args.output_boot.write_bytes(result)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"Wrote {args.output_boot} ({len(result)} bytes)")
    print("Preserved the MTK wrapper, ramdisk, boot arguments, and partition size.")
    print("This only creates a file; it does not flash the tablet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
