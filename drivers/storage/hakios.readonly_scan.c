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
 * Bridge the GPT/APFS scanner to the bounded, chunked read-only block core.
 */
#include <sys/hakios.readonly_scan.h>

static int
readonly_scan_read(void *context, uint64_t lba, uint32_t blocks,
    void *destination)
{
	const struct hakios_readonly_media *media = context;
	uint64_t offset, size, done;

	if (!hakios_readonly_media_valid(media) || blocks == 0 ||
	    lba > UINT64_MAX / media->block_size ||
	    blocks > UINT64_MAX / media->block_size) {
		return -1;
	}
	offset = lba * media->block_size;
	size = (uint64_t)blocks * media->block_size;
	return hakios_readonly_block_read(media, offset, size, destination, NULL, 0,
	    &done) == HAKIOS_READONLY_OK && done == size ? 0 : -1;
}

int
hakios_readonly_gpt_apfs_scan(const struct hakios_readonly_media *media,
    const char *partition_name, void *scratch, size_t scratch_size,
    struct hakios_gpt_apfs_result *result)
{
	if (!hakios_readonly_media_valid(media)) {
		return HAKIOS_GPT_APFS_RANGE;
	}
	return hakios_gpt_apfs_scan(readonly_scan_read, (void *)media,
	    media->block_count, media->block_size, partition_name, scratch,
	    scratch_size, result);
}
