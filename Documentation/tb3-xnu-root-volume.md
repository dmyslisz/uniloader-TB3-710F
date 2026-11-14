# TB3-710F XNU root volume packaging

The loader expects the root disk as a gzip-compressed, raw HFS+ or HFSX volume.
It decompresses the image into the physical range beginning at
`CONFIG_XNU_RAMDISK_PA` (currently `0x90000000`) and exposes it to XNU as
`md0`. The current usable RAM end is `0xBED00000`, so the uncompressed
image, rounded up to 4 KiB, must fit in the range between those values.

`tools/pack_tb3_ramdisk.py` validates the HFS+ volume header and RAM limit,
then writes a deterministic gzip file. It does not make a filesystem, extract
or decrypt an IPSW, include Apple files, or install anything on the tablet.

Example, after obtaining and converting a compatible iOS root volume:

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
