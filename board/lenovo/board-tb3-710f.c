// SPDX-License-Identifier: GPL-2.0
/*
 * Lenovo TB3-710F (MT8127) first-stage framebuffer experiment.
 *
 * Keep LK's DPI/LVDS controller configuration intact.  The only action
 * here is a bounded CPU write to the framebuffer LK handed off.  The
 * base/format are provisional and must be confirmed against this device's
 * LK source or live register state before using this image on hardware.
 */

#include <board.h>
#include <stdint.h>

#define TB3_FB_BASE       0xBEE00000u
#define TB3_FB_WIDTH      1024u
#define TB3_FB_STRIDE     4096u /* observed 32bpp framebuffer */
#define TB3_MARKER_ROWS   24u

static void tb3_fb_marker(void)
{
	volatile uint32_t *fb = (volatile uint32_t *)TB3_FB_BASE;
	unsigned int y, x;

	/* Three broad bars across only the first 24 scanlines (96 KiB). */
	for (y = 0; y < TB3_MARKER_ROWS; y++) {
		volatile uint32_t *row = (volatile uint32_t *)
			((uintptr_t)fb + y * TB3_FB_STRIDE);

		for (x = 0; x < TB3_FB_WIDTH; x++) {
			if (x < TB3_FB_WIDTH / 3)
				row[x] = 0xFFFF0000u; /* ARGB8888 red */
			else if (x < (TB3_FB_WIDTH * 2) / 3)
				row[x] = 0xFF00FF00u; /* ARGB8888 green */
			else
				row[x] = 0xFF0000FFu; /* ARGB8888 blue */
		}
	}
	__asm__ volatile("dsb sy" ::: "memory");
}

void tb3_smoke_wait(void)
{
	/* MT8127 WDT_RESTART: keep LK's inherited watchdog from rebooting us. */
	volatile uint32_t *wdt_restart = (volatile uint32_t *)0x10007008u;

	for (;;) {
		*wdt_restart = 0x1971u;
		__asm__ volatile("dsb sy" ::: "memory");
	}
}

static int tb3_710f_late_init(void)
{
	tb3_fb_marker();
	return 0;
}

struct board_data board_ops = {
	.name = "lenovo-tb3-710f-mt8127",
	.ops = {
		.late_init = tb3_710f_late_init,
	},
	.devices = 0,
	.num_devices = 0,
	.quirks = 0,
};

