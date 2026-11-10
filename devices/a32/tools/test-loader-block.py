#!/usr/bin/env python3
"""Run the production file-backed block service (block_add_file_part + block_poll).

The file is a host memory buffer behind the EFI_FILE contract; no GPT, no UFS
controller and no ARM code are involved.  This proves the loader's read path for
\\EFI\\hakios\\system.apfs, not that the phone has that file or that XNU mounts it.
"""
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
source = (ROOT / "xnuloader/loader.c").read_text()


def section(start, end):
    begin = source.index(start)
    return source[begin:source.index(end, begin)]


add_part = section("static int\nblock_add_file_part(", "static void\nblock_start(")
# the AArch64 memory barrier is not a host instruction; it carries no data-path logic
poll = section("static void\nblock_poll(void)", "static void\ncharger_start(").replace(
    '__asm__ volatile ("dmb sy");', '')

prelude = r'''
#define _GNU_SOURCE
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdint.h>
#include "efi.h"

#define BLOCK_MAGIC        0x4b434f4c42574452ULL
#define BLOCK_VERSION      3
#define BLOCK_MAX_PARTS    160
#define BLOCK_PART_UNIT    1u
#define BLOCK_PART_FILE    2u
#define BLOCK_OP_READ      0u
#define BLOCK_OP_WRITE     1u
#define BLOCK_BUFFER_SIZE  (4u << 20)
#define BLOCK_WRITE_FIRST  2042368ULL
#define READ_SYSREG(r)     0

struct loader_block_part {
	char name[36];
	uint32_t block_size;
	uint64_t blocks;
	uint64_t start_lba;
	uint16_t unit;
	uint8_t lun;
	uint8_t flags;
	uint32_t reserved;
};

struct loader_block {
	uint64_t magic;
	uint32_t version, size;
	uint32_t parts, buffer_size;
	uint64_t buffer_pa;
	uint32_t write_part_plus_one;
	uint32_t write_reserved;
	uint64_t write_first;
	struct {
		volatile uint32_t request;
		uint32_t part;
		uint64_t lba, count;
		uint32_t op;
		uint32_t reserved;
	} ask __attribute__((aligned(128)));
	struct {
		volatile uint32_t answered;
		uint32_t reserved;
		int64_t status;
		uint64_t served, failed, bytes, ticks;
	} answer __attribute__((aligned(128)));
	struct loader_block_part part[BLOCK_MAX_PARTS] __attribute__((aligned(128)));
} __attribute__((aligned(0x2000)));

_Static_assert(__builtin_offsetof(struct loader_block, ask) == 128,
    "the test page must keep the production layout");

static uint8_t block_buffer[BLOCK_BUFFER_SIZE] __attribute__((aligned(0x2000)));
static struct loader_block block_shared;
static efi_block_io *block_bios[BLOCK_MAX_PARTS];
static efi_file *block_file;
static efi_file *block_file_root;
static uint64_t block_file_size;
static int block_write_part = -1;
static uint64_t block_writes, block_writes_refused, block_write_bytes;
static int hc_refused_reads;

static void flush_dcache(uint64_t a, uint64_t b) { (void)a; (void)b; }
static void clean_dcache(uint64_t a, uint64_t b) { (void)a; (void)b; }
static int hc_list_is_uefis(void) { return 1; }
static uint32_t ufs_crc32(const void *p, uint64_t n) { (void)p; (void)n; return 0; }
static void print(const char *fmt, ...) { (void)fmt; }

typedef struct {
	efi_file f;
	const uint8_t *data;
	uint64_t size, pos;
} fake_file;

static fake_file the_file;
static fake_file the_root;
static efi_simple_fs the_fs;
static int no_volume, opens, closes, reads, fault;

static efi_status EFIAPI fake_close(efi_file *self) { (void)self; closes++; return 0; }
static efi_status EFIAPI fake_read(efi_file *self, uint64_t *n, void *buf)
{
	fake_file *ff = (fake_file *)self;
	uint64_t k = *n;

	reads++;
	if (fault == 3) { (*n)++; return 0; }
	if (k > ff->size - ff->pos) {
		k = ff->size - ff->pos;
	}
	memcpy(buf, ff->data + ff->pos, (size_t)k);
	ff->pos += k;
	*n = k;
	return 0;
}
static efi_status EFIAPI fake_set_position(efi_file *self, uint64_t pos)
{
	fake_file *ff = (fake_file *)self;

	if (pos > ff->size) {
		return EFI_ERROR_BIT | 2;
	}
	ff->pos = pos;
	return 0;
}
static efi_status EFIAPI fake_get_info(efi_file *self, const efi_guid *g, uint64_t *n, void *buf)
{
	fake_file *ff = (fake_file *)self;

	(void)g;
	if (*n < 16) {
		return EFI_ERROR_BIT | 5;
	}
	memset(buf, 0, 16);
	memcpy((char *)buf + EFI_FILE_INFO_FILE_SIZE_OFFSET, &ff->size, 8);
	*n = fault == 1 ? 8 : 16;
	return 0;
}
static efi_status EFIAPI fake_open(efi_file *self, efi_file **file, const char16 *name, uint64_t mode, uint64_t attrs)
{
	(void)self; (void)name; (void)mode; (void)attrs;
	opens++;
	*file = &the_file.f;
	return 0;
}
static efi_status EFIAPI fake_open_volume(efi_simple_fs *s, efi_file **root)
{
	(void)s;
	*root = &the_root.f;
	return 0;
}
static efi_status EFIAPI fake_locate(int type, const efi_guid *g, void *key, uint64_t *count, efi_handle **buf)
{
	efi_handle *handles;

	(void)type; (void)g; (void)key;
	if (no_volume) {
		return EFI_ERROR_BIT | 14;
	}
	handles = malloc(sizeof(*handles));
	assert(handles != NULL);
	handles[0] = (efi_handle)(uintptr_t)0x1234;
	*count = 1;
	*buf = handles;
	return 0;
}
static efi_status EFIAPI fake_handle_protocol(efi_handle h, const efi_guid *g, void **iface)
{
	efi_guid fs_guid = EFI_SIMPLE_FILE_SYSTEM_GUID;

	(void)h;
	if (memcmp(g, &fs_guid, sizeof(fs_guid)) == 0) {
		*iface = &the_fs;
		return 0;
	}
	return EFI_ERROR_BIT | 14;
}
static efi_status EFIAPI fake_free_pool(void *p) { free(p); return 0; }

static efi_boot_services services, *BS = &services;
'''

setup = r'''
static uint64_t seq;
static int64_t ask(uint32_t op, uint32_t part, uint64_t lba, uint64_t count)
{
	block_shared.ask.part = part;
	block_shared.ask.lba = lba;
	block_shared.ask.count = count;
	block_shared.ask.op = op;
	block_shared.ask.request = ++seq;
	block_poll();
	assert(block_shared.answer.answered == seq);
	return block_shared.answer.status;
}

int main(int argc, char **argv)
{
	static uint8_t data[10000];
	struct loader_block_part *bp;
	int64_t status;

	for (size_t i = 0; i < sizeof(data); i++) {
		data[i] = (uint8_t)(i * 7 + 3);
	}
	services.locate_handle_buffer = fake_locate;
	services.handle_protocol = fake_handle_protocol;
	services.free_pool = fake_free_pool;

	the_file.data = data;
	the_file.size = sizeof(data);
	the_file.f.close = fake_close;
	the_file.f.read = fake_read;
	the_file.f.set_position = (void *)fake_set_position;
	the_file.f.get_info = fake_get_info;
	the_root.f.open = fake_open;
	the_root.f.close = fake_close;
	the_fs.open_volume = fake_open_volume;

	memset(&block_shared, 0, sizeof(block_shared));

	/* Malformed metadata must not publish a partition; retain correct large sizes. */
	if (argc == 2) {
		fault = atoi(argv[1]);
		if (fault == 1) {
			assert(block_add_file_part() == 0);
			assert(block_shared.parts == 0 && closes == 2);
		} else if (fault == 2) {
			the_file.size = UINT64_MAX;
			assert(block_add_file_part() == 1);
			assert(block_shared.part[0].blocks == 4503599627370496ULL);
		} else {
			assert(block_add_file_part() == 1);
			assert(ask(BLOCK_OP_READ, 0, 0, 1) == (int64_t)(EFI_ERROR_BIT | 10));
			assert(block_shared.answer.failed == 1 && block_shared.answer.bytes == 0);
		}
		printf("PASS: file block boundary scenario %d\n", fault);
		return 0;
	}

	/* no SimpleFS volume: the service is simply absent */
	no_volume = 1;
	assert(block_add_file_part() == 0);
	assert(block_shared.parts == 0);
	no_volume = 0;

	/* a volume with a 10,000-byte file: three 4096-byte blocks, the last short */
	assert(block_add_file_part() == 1);
	assert(block_shared.parts == 1);
	bp = &block_shared.part[0];
	assert(strcmp(bp->name, "apfsfile") == 0);
	assert(bp->block_size == 4096 && bp->blocks == 3 && bp->flags == BLOCK_PART_FILE);
	assert(block_file_size == sizeof(data));
	assert(opens == 1 && block_file == &the_file.f && block_file_root == &the_root.f);

	/* first and second block at their file offsets */
	memset(block_buffer, 0xaa, 4096);
	assert(ask(BLOCK_OP_READ, 0, 0, 1) == 0);
	assert(memcmp(block_buffer, data, 4096) == 0);
	memset(block_buffer, 0xaa, 4096);
	assert(ask(BLOCK_OP_READ, 0, 1, 1) == 0);
	assert(memcmp(block_buffer, data + 4096, 4096) == 0);

	/* the last block is short in the file and must be zero-filled past EOF */
	memset(block_buffer, 0xaa, 4096);
	assert(ask(BLOCK_OP_READ, 0, 2, 1) == 0);
	assert(memcmp(block_buffer, data + 8192, sizeof(data) - 8192) == 0);
	for (size_t i = sizeof(data) - 8192; i < 4096; i++) {
		assert(block_buffer[i] == 0);
	}

	/* a block past the end, and a zero/oversized count: refused before the file is touched */
	assert(ask(BLOCK_OP_READ, 0, 3, 1) == (int64_t)(EFI_ERROR_BIT | 2));
	assert(block_shared.answer.failed == 1);
	assert(ask(BLOCK_OP_READ, 0, 0, 0) == (int64_t)(EFI_ERROR_BIT | 2));
	assert(ask(BLOCK_OP_READ, 0, 0, BLOCK_BUFFER_SIZE / 4096 + 1) == (int64_t)(EFI_ERROR_BIT | 2));
	assert(block_shared.answer.failed == 3);

	/* writes and unknown operations are refused; the file is not touched */
	status = ask(BLOCK_OP_WRITE, 0, 0, 1);
	assert(status == (int64_t)(EFI_ERROR_BIT | 15));
	assert(block_writes_refused == 1);
	assert(ask(7, 0, 0, 1) == (int64_t)(EFI_ERROR_BIT | 15));
	assert(block_writes_refused == 2);
	assert(block_shared.answer.failed == 5);

	/* an answered request is not served twice */
	block_shared.ask.request = block_shared.answer.answered;
	block_poll();
	assert(block_shared.answer.failed == 5);

	puts("PASS: file-backed block service (register, offset reads, EOF zero-fill, bounds, write refusal)");
	return 0;
}
'''

code = prelude + add_part + poll + setup

with tempfile.TemporaryDirectory(prefix="a32-block-test-") as directory:
    cfile = Path(directory) / "test.c"
    binary = Path(directory) / "test"
    cfile.write_text(code)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=undefined", "-fno-sanitize-recover=all",
                    "-I", str(ROOT / "xnuloader"), str(cfile), "-o", str(binary)], check=True)
    results = [subprocess.run([str(binary), *args]).returncode
               for args in ([], ["1"], ["2"], ["3"])]
    if any(results):
        raise SystemExit(f"block test exits: {results}")
