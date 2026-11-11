#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../xnu/files/bsd/sys/hakios.gpt_apfs.h"

#define SECTOR 512u
#define BLOCKS 256u
#define ENTRY_LBA 2u
#define ENTRY_COUNT 5u
#define ENTRY_SIZE 128u
#define PART_FIRST 16u
#define PART_LAST 143u

static uint8_t disk[BLOCKS * SECTOR];
static uint8_t scratch[4096];
static int reads;

static uint32_t
crc32_bytes(const void *data, size_t size)
{
	const uint8_t *p = data;
	uint32_t crc = 0xffffffffu;
	while (size--) {
		crc ^= *p++;
		for (unsigned bit = 0; bit < 8; bit++) {
			crc = (crc >> 1) ^ (0xedb88320u & (0u - (crc & 1u)));
		}
	}
	return ~crc;
}

static void
put32(uint8_t *p, uint32_t value)
{
	for (unsigned i = 0; i < 4; i++) p[i] = (uint8_t)(value >> (8 * i));
}

static void
put64(uint8_t *p, uint64_t value)
{
	for (unsigned i = 0; i < 8; i++) p[i] = (uint8_t)(value >> (8 * i));
}

static int
read_blocks(void *context, uint64_t lba, uint32_t blocks, void *destination)
{
	(void)context;
	reads++;
	if (lba > BLOCKS || blocks > BLOCKS - lba) return -1;
	memcpy(destination, disk + lba * SECTOR, (size_t)blocks * SECTOR);
	return 0;
}

static void
finish_crcs(void)
{
	uint8_t *header = disk + SECTOR;
	uint8_t *entries = disk + ENTRY_LBA * SECTOR;
	put32(header + 88, crc32_bytes(entries, ENTRY_COUNT * ENTRY_SIZE));
	put32(header + 16, 0);
	put32(header + 16, crc32_bytes(header, 92));
}

static void
make_valid(void)
{
	memset(disk, 0, sizeof(disk));
	uint8_t *header = disk + SECTOR;
	uint8_t *entry = disk + ENTRY_LBA * SECTOR;
	memcpy(header, "EFI PART", 8);
	put32(header + 8, 0x00010000u);
	put32(header + 12, 92);
	put64(header + 24, 1);
	put64(header + 32, BLOCKS - 1);
	put64(header + 40, 8);
	put64(header + 48, BLOCKS - 8);
	put64(header + 72, ENTRY_LBA);
	put32(header + 80, ENTRY_COUNT);
	put32(header + 84, ENTRY_SIZE);
	entry[0] = 1; /* non-empty partition type GUID */
	entry[16] = 2; /* unique GUID */
	put64(entry + 32, PART_FIRST);
	put64(entry + 40, PART_LAST);
	const char *name = "xnusys";
	for (size_t i = 0; name[i]; i++) entry[56 + 2 * i] = (uint8_t)name[i];
	uint8_t *nx = disk + PART_FIRST * SECTOR;
	memcpy(nx + 32, "NXSB", 4);
	put32(nx + 36, 4096);
	put64(nx + 40, 16); /* 64 KiB: the minimum accepted APFS container */
	finish_crcs();
	reads = 0;
}

static int
scan(struct hakios_gpt_apfs_result *result)
{
	return hakios_gpt_apfs_scan(read_blocks, NULL, BLOCKS, SECTOR, "xnusys",
	    scratch, sizeof(scratch), result);
}

int
main(void)
{
	struct hakios_gpt_apfs_result result;

	make_valid();
	assert(scan(&result) == HAKIOS_GPT_APFS_OK);
	assert(result.first_lba == PART_FIRST);
	assert(result.partition_blocks == PART_LAST - PART_FIRST + 1);
	assert(result.apfs_bytes == 65536);
	assert(result.apfs_blocks == 128);
	assert(reads == 3); /* header, entries, one APFS superblock */

	make_valid();
	disk[SECTOR + 16] ^= 1;
	assert(scan(&result) == HAKIOS_GPT_APFS_BAD_GPT);

	make_valid();
	disk[ENTRY_LBA * SECTOR + 1] ^= 1;
	assert(scan(&result) == HAKIOS_GPT_APFS_BAD_GPT);

	make_valid();
	put32(disk + SECTOR + 80, 0xffffffffu);
	finish_crcs();
	assert(scan(&result) == HAKIOS_GPT_APFS_RANGE);

	make_valid();
	put64(disk + ENTRY_LBA * SECTOR + 40, BLOCKS + 10);
	finish_crcs();
	assert(scan(&result) == HAKIOS_GPT_APFS_RANGE);

	make_valid();
	memcpy(disk + PART_FIRST * SECTOR + 32, "NOPE", 4);
	assert(scan(&result) == HAKIOS_GPT_APFS_NO_APFS);

	make_valid();
	put64(disk + PART_FIRST * SECTOR + 40, UINT64_MAX);
	assert(scan(&result) == HAKIOS_GPT_APFS_RANGE);

	make_valid();
	put32(disk + PART_FIRST * SECTOR + 36, 2048);
	assert(scan(&result) == HAKIOS_GPT_APFS_RANGE);

	make_valid();
	put64(disk + PART_FIRST * SECTOR + 40, 15);
	assert(scan(&result) == HAKIOS_GPT_APFS_RANGE);

	make_valid();
	assert(hakios_gpt_apfs_scan(read_blocks, NULL, BLOCKS, SECTOR, "other",
	    scratch, sizeof(scratch), &result) == HAKIOS_GPT_APFS_NOT_FOUND);

	make_valid();
	assert(hakios_gpt_apfs_scan(read_blocks, NULL, BLOCKS, SECTOR, "xnusys",
	    scratch, 128, &result) == HAKIOS_GPT_APFS_SCRATCH);

	make_valid();
	uint8_t *tight = malloc(ENTRY_COUNT * ENTRY_SIZE);
	assert(tight != NULL);
	assert(hakios_gpt_apfs_scan(read_blocks, NULL, BLOCKS, SECTOR, "xnusys",
	    tight, ENTRY_COUNT * ENTRY_SIZE, &result) == HAKIOS_GPT_APFS_SCRATCH);
	free(tight);

	puts("PASS: GPT CRC, bounds, partition lookup, and APFS length scan");
	return 0;
}
