#!/usr/bin/env python3
"""Synthetic tests for the TB3-710F MTK-wrapped Android boot repacker."""

import struct
import sys

from pack_tb3_boot import (
    ANDROID_PAGE_SIZE_OFF,
    MTK_KERNEL_HEADER_SIZE,
    MTK_KERNEL_MAGIC,
    MTK_KERNEL_NAME,
    MTK_KERNEL_SIZE_OFF,
    ZIMAGE_MAGIC,
    ZIMAGE_MAGIC_OFF,
    pack,
)


PAGE = 2048
PARTITION_SIZE = 16384


def make_zimage(size: int, marker: int) -> bytes:
    image = bytearray((marker + i) & 0xFF for i in range(size))
    struct.pack_into("<I", image, ZIMAGE_MAGIC_OFF, ZIMAGE_MAGIC)
    return bytes(image)


def make_boot_image() -> tuple[bytes, bytes, bytes, bytes]:
    old_zimage = make_zimage(300, 0x31)
    mtk = bytearray(MTK_KERNEL_HEADER_SIZE)
    mtk[:4] = MTK_KERNEL_MAGIC
    struct.pack_into("<I", mtk, MTK_KERNEL_SIZE_OFF, len(old_zimage))
    mtk[8:16] = MTK_KERNEL_NAME
    kernel = bytes(mtk) + old_zimage
    ramdisk = b"ramdisk-data" * 7
    second = b"second-stage"
    dt = b"device-tree"
    header = bytearray(PAGE)
    header[:8] = b"ANDROID!"
    struct.pack_into("<I", header, 8, len(kernel))
    struct.pack_into("<I", header, 16, len(ramdisk))
    struct.pack_into("<I", header, 24, len(second))
    struct.pack_into("<I", header, ANDROID_PAGE_SIZE_OFF, PAGE)
    struct.pack_into("<I", header, 40, len(dt))
    struct.pack_into("<I", header, 44, 0)
    image = bytearray(header)

    def append_component(component: bytes) -> None:
        image.extend(component)
        image.extend(bytes((-len(component)) % PAGE))

    append_component(kernel)
    append_component(ramdisk)
    append_component(second)
    append_component(dt)
    image.extend(bytes(PARTITION_SIZE - len(image)))
    return bytes(image), ramdisk, second, dt


def expect_value_error(call, label: str) -> None:
    try:
        call()
    except ValueError:
        return
    raise AssertionError(f"{label}: expected ValueError")


def main() -> None:
    original, ramdisk, second, dt = make_boot_image()
    new_zimage = make_zimage(901, 0xA0)
    packed = pack(original, new_zimage)

    assert len(packed) == len(original)
    assert packed[:8] == b"ANDROID!"
    assert struct.unpack_from("<I", packed, 8)[0] == MTK_KERNEL_HEADER_SIZE + len(new_zimage)
    assert struct.unpack_from("<I", packed, PAGE)[0:1] == (int.from_bytes(MTK_KERNEL_MAGIC, "little"),)
    assert struct.unpack_from("<I", packed, PAGE + MTK_KERNEL_SIZE_OFF)[0] == len(new_zimage)
    assert packed[PAGE + MTK_KERNEL_HEADER_SIZE:PAGE + MTK_KERNEL_HEADER_SIZE + len(new_zimage)] == new_zimage

    new_kernel_size = MTK_KERNEL_HEADER_SIZE + len(new_zimage)
    ramdisk_off = PAGE + ((new_kernel_size + PAGE - 1) & ~(PAGE - 1))
    assert packed[ramdisk_off:ramdisk_off + len(ramdisk)] == ramdisk
    second_off = ramdisk_off + ((len(ramdisk) + PAGE - 1) & ~(PAGE - 1))
    assert packed[second_off:second_off + len(second)] == second
    dt_off = second_off + ((len(second) + PAGE - 1) & ~(PAGE - 1))
    assert packed[dt_off:dt_off + len(dt)] == dt

    broken_inner_size = bytearray(original)
    struct.pack_into("<I", broken_inner_size, PAGE + MTK_KERNEL_SIZE_OFF, 1)
    expect_value_error(lambda: pack(bytes(broken_inner_size), new_zimage), "bad MTK inner size")

    unwrapped = bytearray(original)
    unwrapped[PAGE:PAGE + 4] = b"NOPE"
    expect_value_error(lambda: pack(bytes(unwrapped), new_zimage), "missing MTK wrapper")

    bad_zimage = bytearray(new_zimage)
    struct.pack_into("<I", bad_zimage, ZIMAGE_MAGIC_OFF, 0)
    expect_value_error(lambda: pack(original, bytes(bad_zimage)), "bad zImage magic")
    print("TB3-710F MTK boot image repacker checks passed")


if __name__ == "__main__":
    main()
