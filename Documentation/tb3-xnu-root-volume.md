# TB3-710F XNU root volume packaging

The loader's current memory-disk path accepts a gzip-compressed, raw HFS+ or
HFSX volume. It decompresses the image into the physical range beginning at
`CONFIG_XNU_RAMDISK_PA` (currently `0x90000000`) and exposes it to XNU as
`md0`. The current usable RAM end is `0xBED00000`, so the uncompressed
image, rounded up to 4 KiB, must fit in the 785,383,424-byte range between
those values.

A local extraction of the iPad2,5 iOS 7.0 (11A465) IPSW produced an
`Apple_HFSX` root volume of 1,560,113,152 bytes (1,487.84 MiB), with 4 KiB
allocation blocks and zero free blocks in the volume header. This is larger
than the current memory-disk capacity, so this unmodified Apple root volume
cannot be packaged for the current `md0` path. Compressing it does not reduce
the required uncompressed RAM footprint.

## Block-backed root path

The Lenovo MT8127 kernel source identifies MSDC0 as the eMMC host. Its
TB3-710F board configuration uses an 8-bit data bus and the 200 MHz MSDC
clock source; the controller registers are mapped at physical
`0x11230000` (the Linux virtual base is `0xF1230000`). A practical XNU
transport should start with low-speed, read-only PIO and avoid DMA and writes.
The device's eMMC user area is much larger than this root volume.

The XNU tree already has `IOBlockStorageDevice`, `IOStorage`, and
`IOMediaBSDClient` support, plus board-specific PIO SD block-device examples.
The TB3 implementation can follow that model: a native MSDC0/eMMC transport
publishes read-only media, then the existing partition and HFSX code can mount
the root volume. The current TB3 profile does not yet include this transport or
a block-backed root mount. A raw HFSX image must be placed in a dedicated
block range before a hardware root-mount test; do not overwrite LineageOS
partitions as part of driver development.

`tools/pack_tb3_ramdisk.py` validates the HFS+ volume header and RAM limit,
then writes a deterministic gzip file. It does not make a filesystem, extract
or decrypt an IPSW, include Apple files, or install anything on the tablet.

For a different, size-compatible root volume:

```powershell
python tools/pack_tb3_ramdisk.py .\rootfs.raw .\blob\ramdisk
```

The volume needs to come from the same ARMv7 iOS build as the userspace and
dyld shared cache used for the experiment. The XNU/uniLoader repository does
not contain Apple userland, an IPSW, a root image, or a dyld shared cache.
No iOS userspace has been booted yet.

The current early-handoff CI artifact intentionally uses an empty ramdisk.
It is only a kernel/framebuffer bring-up artifact and is not a bootable iOS
image. Do not flash it.
