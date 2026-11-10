/** @file
  DXE-local copy of the validated SEC memory map. No static RAM fallback.
  SPDX-License-Identifier: BSD-2-Clause-Patent
**/
#include <Guid/A32MemoryMapHob.h>
#include <Library/HobLib.h>

STATIC EFI_MEMORY_REGION_DESCRIPTOR mMemoryMap[MAX_ARM_MEMORY_REGION_DESCRIPTOR_COUNT];
STATIC UINT8 mMemoryMapCount;

VOID
GetMemoryMap (
  OUT EFI_MEMORY_REGION_DESCRIPTOR **MemoryDescriptor,
  OUT UINT8 *MemoryDescriptorCount
  )
{
  VOID *Hob;
  EFI_STATUS Status;

  *MemoryDescriptor = NULL;
  *MemoryDescriptorCount = 0;
  // Do not log here: framebuffer DEBUG can re-enter this very getter.
  if (mMemoryMapCount == 0) {
    Hob = GetFirstGuidHob (&gA32MemoryMapHobGuid);
    if ((Hob == NULL) || (GET_HOB_LENGTH (Hob) < sizeof (EFI_HOB_GUID_TYPE))) return;
    Status = A32CopyMemoryMapHob (GET_GUID_HOB_DATA (Hob), GET_GUID_HOB_DATA_SIZE (Hob),
                                mMemoryMap, MAX_ARM_MEMORY_REGION_DESCRIPTOR_COUNT,
                                &mMemoryMapCount);
    if (EFI_ERROR (Status)) return;
  }
  *MemoryDescriptor = mMemoryMap;
  *MemoryDescriptorCount = mMemoryMapCount;
}
