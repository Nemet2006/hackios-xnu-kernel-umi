/** @file
  By-value SEC to DXE memory map. Private to one AARCH64 firmware build.
  SPDX-License-Identifier: BSD-2-Clause-Patent
**/
#ifndef A32_MEMORY_MAP_HOB_H_
#define A32_MEMORY_MAP_HOB_H_

#include <Library/MemoryMapLib.h>
#include <Pi/PiHob.h>

#define A32_MEMORY_MAP_HOB_VERSION  1

typedef struct {
  UINT32 Version;
  UINT32 DescriptorCount;
  UINT32 DescriptorSize;
  UINT32 Reserved;
} A32_MEMORY_MAP_HOB_HEADER;

extern EFI_GUID gA32MemoryMapHobGuid;

// Count is cleared on failure; Destination is untouched until all checks pass.
EFI_STATUS
A32CopyMemoryMapHob (
  IN CONST VOID *Data,
  IN UINTN DataSize,
  OUT EFI_MEMORY_REGION_DESCRIPTOR *Destination,
  IN UINTN Capacity,
  OUT UINT8 *Count
  );

EFI_STATUS
A32PublishMemoryMap (
  IN CONST EFI_MEMORY_REGION_DESCRIPTOR *Map,
  IN UINT8 Count
  );

#endif
