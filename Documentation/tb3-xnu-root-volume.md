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

Booting this userspace therefore requires a block-backed root device in XNU
(for example, read-only eMMC or SD storage) or a separately built smaller
root volume that fits in RAM. The current loader does not implement an eMMC/SD
block driver or mount this HFSX volume as a block device. The existing
`tools/pack_tb3_ramdisk.py` helper should reject this image at its RAM limit.

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
