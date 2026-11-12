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
#ifndef _SYS_HAKIOS_READONLY_SCAN_H_
#define _SYS_HAKIOS_READONLY_SCAN_H_

#include <sys/hakios.gpt_apfs.h>
#include <sys/hakios.readonly_block.h>

int hakios_readonly_gpt_apfs_scan(const struct hakios_readonly_media *media,
    const char *partition_name, void *scratch, size_t scratch_size,
    struct hakios_gpt_apfs_result *result);

#endif /* _SYS_HAKIOS_READONLY_SCAN_H_ */
