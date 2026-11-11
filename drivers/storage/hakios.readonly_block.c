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
 * Bounds and transfer core for read-only block transports. There is
 * deliberately no write callback or write operation in this interface.
 */
#include <sys/hakios.readonly_block.h>

static int
power_of_two(uint32_t value)
{
	return value != 0 && (value & (value - 1)) == 0;
}

static void
copy_bytes(uint8_t *destination, const uint8_t *source, uint64_t size)
{
	while (size--) {
		*destination++ = *source++;
	}
}

int
hakios_readonly_media_valid(const struct hakios_readonly_media *media)
{
	return media != NULL && power_of_two(media->block_size) &&
	    media->block_size >= 512 && media->block_size <= 4096 &&
	    media->block_count != 0 &&
	    media->block_count <= UINT64_MAX / media->block_size &&
	    media->max_transfer_blocks != 0 && media->read_blocks != NULL;
}

int
hakios_readonly_block_read(const struct hakios_readonly_media *media,
    uint64_t byte_offset, uint64_t byte_count, void *destination_storage,
    void *scratch_storage, size_t scratch_size, uint64_t *bytes_read)
{
	uint8_t *destination = destination_storage;
	uint8_t *scratch = scratch_storage;
	uint64_t capacity, remaining;

	if (bytes_read == NULL) {
		return HAKIOS_READONLY_INVALID;
	}
	*bytes_read = 0;
	if (!hakios_readonly_media_valid(media) ||
	    (byte_count != 0 && destination == NULL)) {
		return HAKIOS_READONLY_INVALID;
	}
	capacity = media->block_count * media->block_size;
	if (byte_offset > capacity) {
		return HAKIOS_READONLY_RANGE;
	}
	if (byte_count == 0 || byte_offset == capacity) {
		return HAKIOS_READONLY_OK;
	}
	remaining = byte_count < capacity - byte_offset ? byte_count : capacity - byte_offset;

	while (remaining != 0) {
		uint64_t lba = byte_offset / media->block_size;
		uint32_t within = (uint32_t)(byte_offset % media->block_size);
		if (within != 0 || remaining < media->block_size) {
			if (scratch == NULL || scratch_size < media->block_size) {
				return HAKIOS_READONLY_SCRATCH;
			}
			if (media->read_blocks(media->context, lba, 1, scratch) != 0) {
				return HAKIOS_READONLY_IO;
			}
			uint64_t available = media->block_size - within;
			uint64_t take = remaining < available ? remaining : available;
			copy_bytes(destination, scratch + within, take);
			destination += take;
			byte_offset += take;
			remaining -= take;
			*bytes_read += take;
			continue;
		}

		uint64_t whole = remaining / media->block_size;
		uint32_t blocks = whole > media->max_transfer_blocks ?
		    media->max_transfer_blocks : (uint32_t)whole;
		if (media->read_blocks(media->context, lba, blocks, destination) != 0) {
			return HAKIOS_READONLY_IO;
		}
		uint64_t transferred = (uint64_t)blocks * media->block_size;
		destination += transferred;
		byte_offset += transferred;
		remaining -= transferred;
		*bytes_read += transferred;
	}
	return HAKIOS_READONLY_OK;
}
