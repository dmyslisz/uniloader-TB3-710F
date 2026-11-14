# TB3-710F XNU root volume

## Root filesystem options

The original iPad2,5 iOS 7.0 (11A465) IPSW root volume is an Apple_HFSX
image of 1,560,113,152 bytes (about 1.46 GiB). It is too large for the
current RAM disk range, which ends at 0xBED00000 and starts at
CONFIG_XNU_RAMDISK_PA (0x90000000). Compressing the image does not reduce its
uncompressed RAM requirement.

For the TB3 profile, the image can instead be stored as a file on a FAT32
microSD card:

    IOS7/ROOTFS.HFS

The loader's ARMv7 Mach-O XNU handoff sets tb3_sd=1. The TB3 XNU patch adds a
read-only PIO transport for MSDC1, configures the board's four-bit SD pin mux,
and locates this file on FAT32. The HFSX file is presented as block media to
the existing HFS+ stack. Filesystem writes are held in a volatile copy-on-write
overlay in RAM; they are not written back to the microSD image. The input
image should be extracted from the decrypted IPSW's Apple_HFSX partition
(partition 3) and copied unchanged to the path above.

The TB3 patch also supports a read-only PIO transport for MSDC0 eMMC, but the
default profile selects MSDC1 microSD so it does not require placing an iOS
root image on an eMMC partition.

## Hardware and boot status

The Lenovo MT8127 kernel source configures MSDC1 as the removable four-bit SD
host and uses PMIC rails VMC and VMCH for the card. The current XNU MSDC1
driver does not yet implement that PMIC rail sequence. It also has not been
tested on a cold boot with a card, so the SD power-up and root-volume read
remain unverified on hardware.

CI has built the patched ARMv7 Mach-O kernel and the uniLoader handoff image.
The early-handoff artifact contains uniLoader, mach_kernel, and a minimal
Apple device tree. It is not a complete iOS installation: the root volume is
not bundled, no dyld shared cache is included, and the tablet has not yet
booted XNU or iOS userspace.

The tools/pack_tb3_boot.py script can create an Android boot image using a
read-only backup of the tablet's existing boot image and the built uniLoader
zImage. It preserves the original ramdisk, DTB, boot arguments, MTK wrapper,
and partition size. It only creates a local file; it does not flash the tablet.
