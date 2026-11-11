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
#ifndef _SYS_HAKIOS_GPT_APFS_H_
#define _SYS_HAKIOS_GPT_APFS_H_

#include <stddef.h>
#include <stdint.h>

typedef int (*hakios_block_read_fn)(void *context, uint64_t lba,
    uint32_t blocks, void *destination);

struct hakios_gpt_apfs_result {
	uint64_t first_lba;
	uint64_t partition_blocks;
	uint64_t apfs_bytes;
	uint64_t apfs_blocks;
};

enum {
	HAKIOS_GPT_APFS_OK = 0,
	HAKIOS_GPT_APFS_IO = 1,
	HAKIOS_GPT_APFS_BAD_GPT = 2,
	HAKIOS_GPT_APFS_NOT_FOUND = 3,
	HAKIOS_GPT_APFS_NO_APFS = 4,
	HAKIOS_GPT_APFS_RANGE = 5,
	HAKIOS_GPT_APFS_SCRATCH = 6,
};

int hakios_gpt_apfs_scan(hakios_block_read_fn read_blocks, void *context,
    uint64_t media_blocks, uint32_t logical_block_size,
    const char *partition_name, void *scratch, size_t scratch_size,
    struct hakios_gpt_apfs_result *result);

#endif /* _SYS_HAKIOS_GPT_APFS_H_ */
