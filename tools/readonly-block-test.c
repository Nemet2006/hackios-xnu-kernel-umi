#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "../xnu/files/bsd/sys/hakios.readonly_block.h"

#define BLOCK_SIZE 512u
#define BLOCK_COUNT 32u
static uint8_t media[BLOCK_SIZE * BLOCK_COUNT];
static unsigned calls, fail_call;
static uint32_t largest;

static int
transport_read(void *context, uint64_t lba, uint32_t blocks, void *destination)
{
	(void)context;
	calls++;
	if (calls == fail_call) return -1;
	assert(lba <= BLOCK_COUNT && blocks <= BLOCK_COUNT - lba);
	if (blocks > largest) largest = blocks;
	memcpy(destination, media + lba * BLOCK_SIZE, (size_t)blocks * BLOCK_SIZE);
	return 0;
}

static struct hakios_readonly_media
medium(void)
{
	struct hakios_readonly_media value = {
		.block_size = BLOCK_SIZE,
		.block_count = BLOCK_COUNT,
		.max_transfer_blocks = 3,
		.read_blocks = transport_read,
		.context = NULL,
	};
	calls = fail_call = largest = 0;
	return value;
}

int
main(void)
{
	for (size_t i = 0; i < sizeof(media); i++) media[i] = (uint8_t)(i * 37u + 11u);
	uint8_t output[BLOCK_SIZE * 10], bounce[BLOCK_SIZE];
	uint64_t done;
	struct hakios_readonly_media m = medium();

	assert(hakios_readonly_media_valid(&m));
	assert(hakios_readonly_block_read(&m, 0, sizeof(output), output, bounce,
	    sizeof(bounce), &done) == HAKIOS_READONLY_OK);
	assert(done == sizeof(output) && memcmp(output, media, sizeof(output)) == 0);
	assert(calls == 4 && largest == 3);

	m = medium();
	memset(output, 0, sizeof(output));
	assert(hakios_readonly_block_read(&m, 100, 1000, output, bounce,
	    sizeof(bounce), &done) == HAKIOS_READONLY_OK);
	assert(done == 1000 && memcmp(output, media + 100, 1000) == 0);

	m = medium();
	assert(hakios_readonly_block_read(&m, sizeof(media) - 100, 500, output, bounce,
	    sizeof(bounce), &done) == HAKIOS_READONLY_OK);
	assert(done == 100 && memcmp(output, media + sizeof(media) - 100, 100) == 0);

	m = medium();
	assert(hakios_readonly_block_read(&m, sizeof(media), 1, output, bounce,
	    sizeof(bounce), &done) == HAKIOS_READONLY_OK && done == 0 && calls == 0);
	assert(hakios_readonly_block_read(&m, sizeof(media) + 1, 1, output, bounce,
	    sizeof(bounce), &done) == HAKIOS_READONLY_RANGE && done == 0);
	assert(hakios_readonly_block_read(&m, UINT64_MAX, UINT64_MAX, output, bounce,
	    sizeof(bounce), &done) == HAKIOS_READONLY_RANGE && done == 0);

	m = medium();
	fail_call = 2;
	assert(hakios_readonly_block_read(&m, 0, sizeof(output), output, bounce,
	    sizeof(bounce), &done) == HAKIOS_READONLY_IO);
	assert(done == 3u * BLOCK_SIZE);

	m = medium();
	assert(hakios_readonly_block_read(&m, 1, 1, output, bounce, 16, &done) ==
	    HAKIOS_READONLY_SCRATCH);

	m.block_size = 1000;
	assert(!hakios_readonly_media_valid(&m));
	m = medium(); m.block_count = 0;
	assert(!hakios_readonly_media_valid(&m));
	m = medium(); m.max_transfer_blocks = 0;
	assert(!hakios_readonly_media_valid(&m));
	m = medium(); m.read_blocks = NULL;
	assert(!hakios_readonly_media_valid(&m));

	puts("PASS: read-only block bounds, chunking, partial sectors, EOF, and I/O errors");
	return 0;
}
