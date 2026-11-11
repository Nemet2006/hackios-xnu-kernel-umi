/*
 * Portions Copyright (c) 2026 HakiOS contributors.
 *
 * This file contains Original Code and/or Modifications of Original Code as
 * defined in and subject to the Apple Public Source License Version 2.0.
 * You may not use this file except in compliance with that License. Please
 * obtain a copy at https://opensource.apple.com/apsl/ and read it before use.
 * This software is distributed on an "AS IS" basis, WITHOUT WARRANTY OF ANY
 * KIND, either express or implied.
 *
 * A transport-independent, read-only GPT partition and APFS-container scanner.
 * Device drivers supply block reads; this code never exposes a write operation.
 */
#include <sys/hakios.gpt_apfs.h>

#define GPT_HEADER_LBA 1u
#define GPT_HEADER_MIN_SIZE 92u
#define GPT_NAME_OFFSET 56u
#define GPT_NAME_CODE_UNITS 36u
#define APFS_NX_MAGIC 0x4253584eu /* "NXSB" as little-endian uint32_t */

static uint32_t
le32(const uint8_t *p)
{
	return (uint32_t)p[0] | (uint32_t)p[1] << 8 |
	    (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

static uint64_t
le64(const uint8_t *p)
{
	return (uint64_t)le32(p) | (uint64_t)le32(p + 4) << 32;
}

static void
put32(uint8_t *p, uint32_t value)
{
	for (unsigned i = 0; i < 4; i++) {
		p[i] = (uint8_t)(value >> (8 * i));
	}
}

static int
bytes_equal(const uint8_t *p, const char *text, size_t size)
{
	for (size_t i = 0; i < size; i++) {
		if (p[i] != (uint8_t)text[i]) {
			return 0;
		}
	}
	return 1;
}

static uint32_t
crc32_bytes(const uint8_t *p, uint64_t size)
{
	uint32_t crc = 0xffffffffu;
	while (size--) {
		crc ^= *p++;
		for (unsigned bit = 0; bit < 8; bit++) {
			crc = (crc >> 1) ^ (0xedb88320u & (0u - (crc & 1u)));
		}
	}
	return ~crc;
}

static int
power_of_two(uint32_t value)
{
	return value != 0 && (value & (value - 1)) == 0;
}

static int
range_blocks(uint64_t first, uint64_t count, uint64_t media_blocks)
{
	return first <= media_blocks && count <= media_blocks - first;
}

static int
partition_name_equal(const uint8_t *entry, const char *name)
{
	size_t i = 0;
	for (; i < GPT_NAME_CODE_UNITS && name[i] != 0; i++) {
		if ((uint8_t)name[i] > 0x7f || entry[GPT_NAME_OFFSET + 2 * i] != (uint8_t)name[i] ||
		    entry[GPT_NAME_OFFSET + 2 * i + 1] != 0) {
			return 0;
		}
	}
	if (name[i] != 0) {
		return 0;
	}
	for (; i < GPT_NAME_CODE_UNITS; i++) {
		if (entry[GPT_NAME_OFFSET + 2 * i] != 0 || entry[GPT_NAME_OFFSET + 2 * i + 1] != 0) {
			return 0;
		}
	}
	return 1;
}

static int
nonzero_guid(const uint8_t *entry)
{
	uint8_t any = 0;
	for (unsigned i = 0; i < 16; i++) {
		any |= entry[i];
	}
	return any != 0;
}

int
hakios_gpt_apfs_scan(hakios_block_read_fn read_blocks, void *context,
    uint64_t media_blocks, uint32_t logical_block_size,
    const char *partition_name, void *scratch_storage, size_t scratch_size,
    struct hakios_gpt_apfs_result *result)
{
	uint8_t *scratch = scratch_storage;
	uint64_t entries_lba, entries_bytes, entries_blocks;
	uint64_t first_usable, last_usable, first = 0, last = 0;
	uint32_t entry_count, entry_size;

	if (read_blocks == NULL || partition_name == NULL || partition_name[0] == 0 ||
	    scratch == NULL || result == NULL || media_blocks <= GPT_HEADER_LBA ||
	    !power_of_two(logical_block_size) || logical_block_size < 512 ||
	    logical_block_size > 4096) {
		return HAKIOS_GPT_APFS_RANGE;
	}
	if (scratch_size < logical_block_size) {
		return HAKIOS_GPT_APFS_SCRATCH;
	}
	if (read_blocks(context, GPT_HEADER_LBA, 1, scratch) != 0) {
		return HAKIOS_GPT_APFS_IO;
	}
	if (!bytes_equal(scratch, "EFI PART", 8)) {
		return HAKIOS_GPT_APFS_BAD_GPT;
	}
	uint32_t header_size = le32(scratch + 12);
	uint32_t header_crc = le32(scratch + 16);
	if (header_size < GPT_HEADER_MIN_SIZE || header_size > logical_block_size ||
	    le64(scratch + 24) != GPT_HEADER_LBA || le64(scratch + 32) >= media_blocks) {
		return HAKIOS_GPT_APFS_BAD_GPT;
	}
	put32(scratch + 16, 0);
	uint32_t calculated_header_crc = crc32_bytes(scratch, header_size);
	put32(scratch + 16, header_crc);
	if (calculated_header_crc != header_crc) {
		return HAKIOS_GPT_APFS_BAD_GPT;
	}

	first_usable = le64(scratch + 40);
	last_usable = le64(scratch + 48);
	entries_lba = le64(scratch + 72);
	entry_count = le32(scratch + 80);
	entry_size = le32(scratch + 84);
	uint32_t entries_crc = le32(scratch + 88);
	if (first_usable == 0 || last_usable < first_usable || last_usable >= media_blocks ||
	    entry_count == 0 || entry_count > 128 || entry_size < 128 || (entry_size & 7) != 0 ||
	    (uint64_t)entry_count > UINT64_MAX / entry_size) {
		return HAKIOS_GPT_APFS_RANGE;
	}
	entries_bytes = (uint64_t)entry_count * entry_size;
	if (entries_bytes > scratch_size || entries_bytes > UINT64_MAX - (logical_block_size - 1)) {
		return HAKIOS_GPT_APFS_SCRATCH;
	}
	entries_blocks = (entries_bytes + logical_block_size - 1) / logical_block_size;
	if (entries_blocks > scratch_size / logical_block_size) {
		return HAKIOS_GPT_APFS_SCRATCH;
	}
	if (entries_blocks > UINT32_MAX || !range_blocks(entries_lba, entries_blocks, media_blocks)) {
		return HAKIOS_GPT_APFS_RANGE;
	}
	if (read_blocks(context, entries_lba, (uint32_t)entries_blocks, scratch) != 0) {
		return HAKIOS_GPT_APFS_IO;
	}
	if (crc32_bytes(scratch, entries_bytes) != entries_crc) {
		return HAKIOS_GPT_APFS_BAD_GPT;
	}

	for (uint32_t i = 0; i < entry_count; i++) {
		const uint8_t *entry = scratch + (uint64_t)i * entry_size;
		if (!nonzero_guid(entry) || !partition_name_equal(entry, partition_name)) {
			continue;
		}
		first = le64(entry + 32);
		last = le64(entry + 40);
		if (first < first_usable || last > last_usable || last < first || last >= media_blocks) {
			return HAKIOS_GPT_APFS_RANGE;
		}
		break;
	}
	if (first == 0) {
		return HAKIOS_GPT_APFS_NOT_FOUND;
	}

	uint64_t partition_blocks = last - first + 1;
	if (partition_blocks > UINT64_MAX / logical_block_size) {
		return HAKIOS_GPT_APFS_RANGE;
	}
	uint64_t partition_bytes = partition_blocks * logical_block_size;
	uint64_t at = 0;
	while (at < partition_bytes) {
		if (at % logical_block_size != 0 ||
		    read_blocks(context, first + at / logical_block_size, 1, scratch) != 0) {
			return HAKIOS_GPT_APFS_IO;
		}
		if (le32(scratch + 32) != APFS_NX_MAGIC) {
			break;
		}
		uint32_t apfs_block_size = le32(scratch + 36);
		uint64_t apfs_block_count = le64(scratch + 40);
		uint64_t remaining = partition_bytes - at;
		if (!power_of_two(apfs_block_size) || apfs_block_size < 4096 || apfs_block_size > 65536 ||
		    apfs_block_count < 16 || apfs_block_count > remaining / apfs_block_size) {
			return HAKIOS_GPT_APFS_RANGE;
		}
		uint64_t container_bytes = apfs_block_count * apfs_block_size;
		if (container_bytes % logical_block_size != 0) {
			return HAKIOS_GPT_APFS_RANGE;
		}
		at += container_bytes;
	}
	if (at == 0) {
		return HAKIOS_GPT_APFS_NO_APFS;
	}

	result->first_lba = first;
	result->partition_blocks = partition_blocks;
	result->apfs_bytes = at;
	result->apfs_blocks = at / logical_block_size;
	return HAKIOS_GPT_APFS_OK;
}
