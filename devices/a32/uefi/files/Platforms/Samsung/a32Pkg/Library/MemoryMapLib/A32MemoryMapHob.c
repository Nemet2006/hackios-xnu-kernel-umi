/** @file
  Validate the private by-value memory map without allocation or debug output.
  SPDX-License-Identifier: BSD-2-Clause-Patent
**/
#include <Guid/A32MemoryMapHob.h>
#include <Library/BaseMemoryLib.h>

STATIC_ASSERT (sizeof (A32_MEMORY_MAP_HOB_HEADER) == 16, "HOB header layout");
STATIC_ASSERT (MAX_ARM_MEMORY_REGION_DESCRIPTOR_COUNT <= 255, "UINT8 map count");

EFI_STATUS
A32CopyMemoryMapHob (
  IN CONST VOID *Data,
  IN UINTN DataSize,
  OUT EFI_MEMORY_REGION_DESCRIPTOR *Destination,
  IN UINTN Capacity,
  OUT UINT8 *Count
  )
{
  A32_MEMORY_MAP_HOB_HEADER Header;
  EFI_MEMORY_REGION_DESCRIPTOR Entry;
  UINTN Bytes, Required, Aligned, Index, NameIndex;
  CONST UINT8 *Entries;

  if (Count == NULL) return EFI_INVALID_PARAMETER;
  *Count = 0;
  if ((Data == NULL) || (Destination == NULL)) return EFI_INVALID_PARAMETER;
  if ((DataSize < sizeof (Header)) ||
      (DataSize > MAX_UINT16 - sizeof (EFI_HOB_GUID_TYPE))) return EFI_COMPROMISED_DATA;
  CopyMem (&Header, Data, sizeof (Header));
  if ((Header.Version != A32_MEMORY_MAP_HOB_VERSION) || (Header.Reserved != 0) ||
      (Header.DescriptorSize != sizeof (Entry)) || (Header.DescriptorCount == 0) ||
      (Header.DescriptorCount > MAX_ARM_MEMORY_REGION_DESCRIPTOR_COUNT) ||
      (Header.DescriptorCount > Capacity)) return EFI_COMPROMISED_DATA;
  // The bounded count makes both multiplication and the alignment addition safe.
  Bytes = (UINTN)Header.DescriptorCount * sizeof (Entry);
  Required = sizeof (Header) + Bytes;
  Aligned = (Required + 7) & ~(UINTN)7;
  if ((Aligned > (MAX_UINT16 & ~(UINTN)7) - sizeof (EFI_HOB_GUID_TYPE)) ||
      (DataSize < Required) || (DataSize > Aligned)) return EFI_COMPROMISED_DATA;

  Entries = (CONST UINT8 *)Data + sizeof (Header);
  for (Index = 0; Index < Header.DescriptorCount; Index++) {
    CopyMem (&Entry, Entries + Index * sizeof (Entry), sizeof (Entry));
    if ((Entry.Length == 0) || (Entry.Address > MAX_UINT64 - Entry.Length)) {
      return EFI_COMPROMISED_DATA;
    }
    for (NameIndex = 0; NameIndex < sizeof (Entry.Name); NameIndex++) {
      if (Entry.Name[NameIndex] == '\0') break;
    }
    if (NameIndex == sizeof (Entry.Name)) return EFI_COMPROMISED_DATA;
  }
  CopyMem (Destination, Entries, Bytes);
  *Count = (UINT8)Header.DescriptorCount;
  return EFI_SUCCESS;
}
