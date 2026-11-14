# TB3-710F XNU root volume

## Root filesystem options

The original iPad2,5 iOS 7.0 (11A465) IPSW root volume is an Apple_HFSX
image of 1,560,113,152 bytes (about 1.46 GiB). It is too large for the
current RAM disk range, which ends at 0xBED00000 and starts at
CONFIG_XNU_RAMDISK_PA (0x90000000). Compressing the image does not reduce its
uncompressed RAM requirement.

For the TB3 profile, store the image as a file on a FAT32 microSD card:

    IOS7/ROOTFS.HFS

The loader's ARMv7 Mach-O XNU handoff sets tb3_sd=1. The TB3 XNU patch adds a
read-only PIO transport for MSDC1, configures the board's four-bit SD pin mux,
and locates this file on FAT32. The HFSX file is presented as block media to
the existing HFS+ stack. Filesystem writes are held in a volatile copy-on-write
overlay in RAM; they are not written back to the microSD image. Extract the
decrypted IPSW's Apple_HFSX partition (partition 3) and copy it unchanged to
the path above.

The TB3 patch also supports a read-only PIO transport for MSDC0 eMMC, but the
default profile selects MSDC1 microSD so it does not require placing an iOS
root image on an eMMC partition.

## Verified root-volume metadata

The extracted partition reports an HFSX volume with 4,096-byte allocation
blocks, 380,887 total blocks, and a size of 1,560,113,152 bytes. Its volume
header points to journal-info block 33. The journal-info block marks the
volume as journaled; the journal header has matching start and end offsets
(0x005A0800), with an 8 MiB journal. This snapshot therefore shows no
outstanding journal range to replay.

The HFSX directory listing includes /sbin/launchd and
/System/Library/Caches/com.apple.dyld/dyld_shared_cache_armv7. This confirms
the expected ARMv7 iOS startup files are present in the image listing; it
does not prove the tablet can read or execute them.

## Hardware and boot status

The Lenovo MT8127 kernel source configures MSDC1 as the removable four-bit SD
host. The project defconfig selects the MT6323 PMIC. The XNU patch now programs
the VMC and VMCH 3.3 V selectors and enables those rails through the initialized
PMIC Wrapper, following the Lenovo kernel's MSDC1 sequence. PMIC access has a
bounded timeout and the SD driver stops if the wrapper is not ready.

CI has built the patched ARMv7 Mach-O kernel and the uniLoader handoff image.
The early-handoff artifact contains uniLoader, mach_kernel, and a minimal
Apple device tree. The rail sequence, SD card initialization, HFSX file read,
and root mount have not yet been verified on the tablet. The artifact does
not include the root volume or a separately embedded dyld shared cache, and no
iOS userspace boot has been demonstrated.

The tools/pack_tb3_boot.py script can create an Android boot image using a
read-only backup of the tablet's existing boot image and the built uniLoader
zImage. It preserves the original ramdisk, DTB, boot arguments, MTK wrapper,
and partition size. It only creates a local file; it does not flash the tablet.
