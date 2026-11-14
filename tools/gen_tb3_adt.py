#!/usr/bin/env python3
"""Build a minimal Apple flattened device tree for TB3-710F XNU bring-up.

This is the legacy XNU DeviceTreeNode format, not an Android/Linux FDT.
It carries only confirmed board identity, RAM range, chosen boot args, and
the single CPU enabled by the current UP-only XNU port. It is an early
bring-up handoff tree, not a complete IOKit driver description.
"""
from pathlib import Path
import struct
import sys

RAM_BASE = 0x80000000
RAM_SIZE = 0x3ED00000
BOOT_ARGS = "-v keepsyms=1 debug=0x14e rd=md0"


def prop(name, value):
    key = name.encode("ascii")
    if not key or len(key) >= 32:
        raise ValueError(f"invalid Apple DT property name: {name!r}")
    return key + bytes(32 - len(key)) + struct.pack("<I", len(value)) + value + bytes((-len(value)) & 3)


def string(value):
    return value.encode("ascii") + b"\0"


def cell(value):
    return struct.pack(">I", value)


def node(properties, children=()):
    props = [("name", string(properties.pop("name")))] + list(properties.items())
    out = bytearray(struct.pack("<II", len(props), len(children)))
    for key, value in props:
        out += prop(key, value)
    for child in children:
        out += child
    return bytes(out)


def build():
    chosen = node({
        "name": "chosen",
        "firmware-version": string("uniLoader/TB3-710F"),
        "boot-args": string(BOOT_ARGS),
    })
    memory = node({
        "name": "memory",
        "device_type": string("memory"),
        "reg": cell(RAM_BASE) + cell(RAM_SIZE),
    })
    cpu0 = node({
        "name": "cpu",
        "device_type": string("cpu"),
        "reg": cell(0),
        "compatible": string("arm,cortex-a7"),
        "status": string("okay"),
    })
    cpus = node({"name": "cpus", "#address-cells": cell(1), "#size-cells": cell(0)}, [cpu0])
    return node({
        "name": "mt8127_tb3",
        "model": string("Lenovo TB3-710F"),
        "compatible": string("mediatek,mt8127"),
        "#address-cells": cell(1),
        "#size-cells": cell(1),
    }, [chosen, memory, cpus])


def validate(data):
    def read_node(pos):
        if pos + 8 > len(data):
            raise ValueError("truncated node header")
        nprops, nchildren = struct.unpack_from("<II", data, pos)
        if nprops == 0:
            raise ValueError("XNU skipProperties requires at least one property per node")
        pos += 8
        names = []
        for _ in range(nprops):
            if pos + 36 > len(data):
                raise ValueError("truncated property header")
            name = data[pos:pos + 32].split(b"\0", 1)[0].decode("ascii")
            length = struct.unpack_from("<I", data, pos + 32)[0]
            end = pos + 36 + ((length + 3) & ~3)
            if end > len(data):
                raise ValueError("truncated property value")
            names.append(name)
            pos = end
        if "name" not in names:
            raise ValueError("node missing required name property")
        for _ in range(nchildren):
            pos = read_node(pos)
        return pos

    end = read_node(0)
    if end != len(data):
        raise ValueError(f"trailing bytes: parsed {end}, file has {len(data)}")
    if RAM_BASE + RAM_SIZE != 0xBED00000:
        raise ValueError("RAM range no longer matches the observed TB3-710F map")


if __name__ == "__main__":
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "blob/dtb")
    image = build()
    validate(image)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(image)
    print(f"TB3 Apple DT: {len(image)} bytes -> {output}")
