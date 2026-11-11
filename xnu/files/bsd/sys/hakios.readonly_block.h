/*
 * Portions Copyright (c) 2026 HakiOS contributors.
 *
 * This file contains Original Code and/or Modifications of Original Code as
 * defined in and subject to the Apple Public Source License Version 2.0.
 * You may not use this file except in compliance with that License. Please
 * obtain a copy at https://opensource.apple.com/apsl/ and read it before use.
 * This software is distributed on an "AS IS" basis, WITHOUT WARRANTY OF ANY
 * KIND, either express or implied.
 */
#ifndef _SYS_HAKIOS_READONLY_BLOCK_H_
#define _SYS_HAKIOS_READONLY_BLOCK_H_

#include <stddef.h>
#include <stdint.h>

typedef int (*hakios_read_blocks_fn)(void *context, uint64_t lba,
    uint32_t blocks, void *destination);

struct hakios_readonly_media {
	uint32_t block_size;
	uint64_t block_count;
	uint32_t max_transfer_blocks;
	hakios_read_blocks_fn read_blocks;
	void *context;
};

enum {
	HAKIOS_READONLY_OK = 0,
	HAKIOS_READONLY_INVALID = 1,
	HAKIOS_READONLY_RANGE = 2,
	HAKIOS_READONLY_IO = 3,
	HAKIOS_READONLY_SCRATCH = 4,
};

int hakios_readonly_media_valid(const struct hakios_readonly_media *media);
int hakios_readonly_block_read(const struct hakios_readonly_media *media,
    uint64_t byte_offset, uint64_t byte_count, void *destination,
    void *scratch, size_t scratch_size, uint64_t *bytes_read);

#endif /* _SYS_HAKIOS_READONLY_BLOCK_H_ */
