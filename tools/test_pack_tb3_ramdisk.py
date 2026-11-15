#!/usr/bin/env python3
"""Small synthetic-volume checks for pack_tb3_ramdisk.py."""
import gzip
import runpy
import struct
import tempfile
from pathlib import Path


def synthetic_hfsplus():
    image = bytearray(4096)
    struct.pack_into(">HH", image, 1024, 0x482B, 4)  # H+, version 4
    struct.pack_into(">II", image, 1064, 512, 8)    # 8 x 512-byte blocks
    return bytes(image)


def main():
    pack = runpy.run_path(str(Path(__file__).with_name("pack_tb3_ramdisk.py")))["pack"]
    with tempfile.TemporaryDirectory(prefix="tb3-ramdisk-check-") as temp:
        root = Path(temp)
        source = root / "volume.raw"
        first = root / "volume-1.gz"
        second = root / "volume-2.gz"
        raw = synthetic_hfsplus()
        source.write_bytes(raw)

        pack(source, first, 0x90000000, 0xBED00000)
        pack(source, second, 0x90000000, 0xBED00000)
        if gzip.decompress(first.read_bytes()) != raw:
            raise SystemExit("gzip round-trip did not preserve the raw HFS+ volume")
        if first.read_bytes() != second.read_bytes():
            raise SystemExit("gzip output is not deterministic")

        try:
            pack(source, root / "too-large.gz", 0xBECFF800, 0xBED00000)
        except ValueError as exc:
            if "capacity" not in str(exc):
                raise
        else:
            raise SystemExit("RAM-window overflow was not rejected")

        invalid = root / "invalid.raw"
        invalid.write_bytes(bytes(4096))
        try:
            pack(invalid, root / "invalid.gz", 0x90000000, 0xBED00000)
        except ValueError as exc:
            if "HFS+" not in str(exc):
                raise
        else:
            raise SystemExit("non-HFS+ input was not rejected")

    print("HFS+ ramdisk packer checks passed")


if __name__ == "__main__":
    main()
