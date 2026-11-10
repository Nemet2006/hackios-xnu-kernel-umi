/** @file
  Early SM-A325F UEFI map. Only the low boot window and DTB-confirmed MMIO are
  described here. This deliberately does not publish the rest of RAM or a
  framebuffer until LK's live reservations and scanout are validated.

  SPDX-License-Identifier: BSD-2-Clause-Patent
**/
#include <Library/MemoryMapLib.h>
#include <Library/BaseLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/DebugLib.h>
#include <Library/FdtLib.h>
#include <Library/PrintLib.h>
#include <Library/HobLib.h>
#include <Guid/A32MemoryMapHob.h>

#define A32_MAX_RANGES       64
#define A32_MAX_RAM_BYTES    ((UINT64)SIZE_1GB * 2 + SIZE_512MB)
#define A32_MIN_PIECE_BYTES  SIZE_16MB
#define A32_PAGE_MASK        ((UINT64)SIZE_4KB - 1)

typedef struct {
  UINT64  Base;
  UINT64  End;
} A32_RANGE;

STATIC EFI_MEMORY_REGION_DESCRIPTOR gMemoryDescriptor[] = {
  // Name, Address, Length, HobOption, ResourceType, ResourceAttribute, MemoryType, ArmAttribute
  {"UEFI Stack",         0x40000000, 0x00040000, AddMem, SYS_MEM, SYS_MEM_CAP, BsData, WRITE_BACK},
  {"UEFI FD",            0x40080000, 0x00300000, AddMem, SYS_MEM, SYS_MEM_CAP, BsData, WRITE_BACK},
  {"DXE Heap",           0x40380000, 0x03C00000, AddMem, SYS_MEM, SYS_MEM_CAP, Conv,   WRITE_BACK},

  {"GIC Distributor",    0x0C000000, 0x00040000, AddDev, MMAP_IO, UNCACHEABLE, MmIO,   NS_DEVICE},
  {"GIC Redistributors", 0x0C040000, 0x00200000, AddDev, MMAP_IO, UNCACHEABLE, MmIO,   NS_DEVICE},
  {"Top Ck Gen",         0x10000000, 0x00001000, AddDev, MMAP_IO, UNCACHEABLE, MmIO,   NS_DEVICE},
  {"Infra Cfg AO",       0x10001000, 0x00001000, AddDev, MMAP_IO, UNCACHEABLE, MmIO,   NS_DEVICE},
  {"Pinctrl",            0x10005000, 0x00001000, AddDev, MMAP_IO, UNCACHEABLE, MmIO,   NS_DEVICE},
  {"WatchDog Timer",     0x10007000, 0x00001000, AddDev, MMAP_IO, UNCACHEABLE, MmIO,   NS_DEVICE},
  {"AP Mixed",          0x1000C000, 0x00001000, AddDev, MMAP_IO, UNCACHEABLE, MmIO,   NS_DEVICE},
  {"PMIC Wrapper",      0x1000D000, 0x00001000, AddDev, MMAP_IO, UNCACHEABLE, MmIO,   NS_DEVICE},
  {"Keypad",            0x10010000, 0x00001000, AddDev, MMAP_IO, UNCACHEABLE, MmIO,   NS_DEVICE},
  {"EMI",               0x10219000, 0x00001000, AddDev, MMAP_IO, UNCACHEABLE, MmIO,   NS_DEVICE},
  {"MSDC-0",            0x11230000, 0x00010000, AddDev, MMAP_IO, UNCACHEABLE, MmIO,   NS_DEVICE},
  {"MSDC-1",            0x11240000, 0x00010000, AddDev, MMAP_IO, UNCACHEABLE, MmIO,   NS_DEVICE},
  {"MSDC Top-0",        0x11CD0000, 0x00001000, AddDev, MMAP_IO, UNCACHEABLE, MmIO,   NS_DEVICE},
  {"MSDC Top-1",        0x11C90000, 0x00001000, AddDev, MMAP_IO, UNCACHEABLE, MmIO,   NS_DEVICE},
  {"Display OVL",       0x1400B000, 0x00001000, AddDev, MMAP_IO, UNCACHEABLE, MmIO,   NS_DEVICE},
};

STATIC EFI_MEMORY_REGION_DESCRIPTOR gFdtMemoryDescriptor[MAX_ARM_MEMORY_REGION_DESCRIPTOR_COUNT];
STATIC UINT8 gFdtMemoryDescriptorCount;

EFI_STATUS
A32PublishMemoryMap (IN CONST EFI_MEMORY_REGION_DESCRIPTOR *Map, IN UINT8 Count)
{
  struct {
    A32_MEMORY_MAP_HOB_HEADER Header;
    EFI_MEMORY_REGION_DESCRIPTOR Entries[MAX_ARM_MEMORY_REGION_DESCRIPTOR_COUNT];
  } Packet;
  EFI_STATUS Status;
  UINTN DataSize;
  UINT8 ValidatedCount;
  VOID *Data;

  if ((Map == NULL) || (Count == 0) || (Count > MAX_ARM_MEMORY_REGION_DESCRIPTOR_COUNT)) {
    return EFI_INVALID_PARAMETER;
  }
  Packet.Header.Version = A32_MEMORY_MAP_HOB_VERSION;
  Packet.Header.DescriptorCount = Count;
  Packet.Header.DescriptorSize = sizeof (*Map);
  Packet.Header.Reserved = 0;
  CopyMem (Packet.Entries, Map, Count * sizeof (*Map));
  DataSize = sizeof (Packet.Header) + Count * sizeof (*Map);
  Status = A32CopyMemoryMapHob (&Packet, DataSize, Packet.Entries,
                              ARRAY_SIZE (Packet.Entries), &ValidatedCount);
  if (EFI_ERROR (Status)) return Status;
  if (GetFirstGuidHob (&gA32MemoryMapHobGuid) != NULL) return EFI_ALREADY_STARTED;
  Data = BuildGuidHob (&gA32MemoryMapHobGuid, DataSize);
  if (Data == NULL) return EFI_OUT_OF_RESOURCES;
  CopyMem (Data, &Packet, DataSize);
  return EFI_SUCCESS;
}

STATIC
BOOLEAN
BootstrapRangeAllowed (UINT64 Base, UINT64 Size, CONST A32_RANGE *Banks, UINTN BankCount,
                       CONST A32_RANGE *Reserved, UINTN ReservedCount)
{
  UINTN Index;
  UINT64 End;
  BOOLEAN Contained = FALSE;
  if (Size == 0 || Base > MAX_UINT64 - Size) return FALSE;
  End = Base + Size;
  for (Index = 0; Index < BankCount; Index++) {
    if (Base >= Banks[Index].Base && End <= Banks[Index].End) {
      Contained = TRUE;
      break;
    }
  }
  if (!Contained) return FALSE;
  for (Index = 0; Index < ReservedCount; Index++) {
    if (Base < Reserved[Index].End && Reserved[Index].Base < End) return FALSE;
  }
  return TRUE;
}

STATIC
UINT64
ReadCells (CONST UINT8 *Data, UINT32 Cells)
{
  if (Cells == 2) {
    return Fdt64ToCpu (ReadUnaligned64 (Data));
  }
  return Fdt32ToCpu (ReadUnaligned32 (Data));
}

STATIC
EFI_STATUS
CollectReg (CONST VOID *Fdt, INT32 Node, UINT32 AddressCells, UINT32 SizeCells,
            A32_RANGE *Ranges, UINTN *Count, BOOLEAN Required)
{
  CONST UINT8 *Reg;
  INT32 Length;
  UINT32 EntrySize;
  INT32 Offset;

  Reg = FdtGetProp (Fdt, Node, "reg", &Length);
  if (Reg == NULL) {
    return Required ? EFI_NOT_FOUND : EFI_SUCCESS;
  }
  EntrySize = (AddressCells + SizeCells) * sizeof (UINT32);
  if ((Length <= 0) || (EntrySize == 0) || ((Length % (INT32)EntrySize) != 0)) {
    return EFI_COMPROMISED_DATA;
  }
  for (Offset = 0; Offset < Length; Offset += EntrySize) {
    UINT64 Base = ReadCells (Reg + Offset, AddressCells);
    UINT64 Size = ReadCells (Reg + Offset + AddressCells * sizeof (UINT32), SizeCells);
    if ((Size == 0) || (Base + Size <= Base) || (*Count >= A32_MAX_RANGES)) {
      return EFI_COMPROMISED_DATA;
    }
    Ranges[*Count].Base = Base;
    Ranges[*Count].End = Base + Size;
    (*Count)++;
  }
  return EFI_SUCCESS;
}

STATIC
EFI_STATUS
SubtractRange (A32_RANGE *Pieces, UINTN *PieceCount, A32_RANGE Cut)
{
  A32_RANGE Out[A32_MAX_RANGES];
  UINTN OutCount = 0;
  UINTN Index;

  for (Index = 0; Index < *PieceCount; Index++) {
    A32_RANGE Part = Pieces[Index];
    if ((Cut.End <= Part.Base) || (Cut.Base >= Part.End)) {
      if (OutCount >= A32_MAX_RANGES) return EFI_OUT_OF_RESOURCES;
      Out[OutCount++] = Part;
      continue;
    }
    if (Cut.Base > Part.Base) {
      if (OutCount >= A32_MAX_RANGES) return EFI_OUT_OF_RESOURCES;
      Out[OutCount].Base = Part.Base;
      Out[OutCount++].End = Cut.Base;
    }
    if (Cut.End < Part.End) {
      if (OutCount >= A32_MAX_RANGES) return EFI_OUT_OF_RESOURCES;
      Out[OutCount].Base = Cut.End;
      Out[OutCount++].End = Part.End;
    }
  }
  CopyMem (Pieces, Out, OutCount * sizeof (A32_RANGE));
  *PieceCount = OutCount;
  return EFI_SUCCESS;
}

/**
  Construct the early A32 MMU map from LK's live FDT.  Dynamic reserved-memory
  nodes (size without reg) are Linux allocation requests and do not describe a
  physical reservation at LK handoff; fixed reservations, the FDT, initrd,
  framebuffer, and the UEFI's own memory are excluded from available RAM.
**/
EFI_STATUS
GetMemoryMapFromFdt (IN CONST VOID *Fdt,
                     OUT EFI_MEMORY_REGION_DESCRIPTOR **MemoryDescriptor,
                     OUT UINT8 *MemoryDescriptorCount)
{
  EFI_STATUS Status;
  INT32 Root, Node, Reserved, Chosen, Length;
  UINT32 AddressCells, SizeCells, ResAddress, ResSize;
  CONST CHAR8 *Type;
  CONST VOID *StartProp, *EndProp, *HighProp, *LowProp, *FbSizeProp;
  INT32 StartLength, EndLength, HighLength, LowLength, FbSizeLength;
  A32_RANGE Banks[A32_MAX_RANGES], ReservedRanges[A32_MAX_RANGES];
  A32_RANGE Pieces[A32_MAX_RANGES];
  UINTN BankCount = 0, ReservedCount = 0, PieceCount, Index, Other, Added;
  UINT64 TotalRam = 0, UsableRam = 0, Base, Size, Start, End, FbBase, FbSize;
  BOOLEAN FbPresent = FALSE;
  INTN ReserveCount, ReserveIndex;
  UINT8 Count;

  gFdtMemoryDescriptorCount = 0;
  if (MemoryDescriptor == NULL || MemoryDescriptorCount == NULL) return EFI_INVALID_PARAMETER;
  *MemoryDescriptor = NULL;
  *MemoryDescriptorCount = 0;
  // The numerical envelope is the existing A32 entry contract, not proof of mapped RAM.
  Base = (UINT64)(UINTN)Fdt;
  if ((Base & 7) != 0 || Base < 0x40000000ULL ||
      Base > 0x140000000ULL - sizeof (FDT_HEADER)) return EFI_INVALID_PARAMETER;
  if (FdtCheckHeader (Fdt) != 0) return EFI_INVALID_PARAMETER;
  Size = FdtTotalSize (Fdt);
  if (Size < sizeof (FDT_HEADER) || Size > 16 * SIZE_1MB ||
      Size > 0x140000000ULL - Base) return EFI_COMPROMISED_DATA;
  Root = FdtPathOffset (Fdt, "/");
  if (Root < 0) return EFI_COMPROMISED_DATA;
  AddressCells = (UINT32)FdtAddressCells (Fdt, Root);
  SizeCells = (UINT32)FdtSizeCells (Fdt, Root);
  if (((AddressCells != 1) && (AddressCells != 2)) || ((SizeCells != 1) && (SizeCells != 2))) {
    return EFI_UNSUPPORTED;
  }

  for (Node = FdtFirstSubnode (Fdt, Root); Node >= 0; Node = FdtNextSubnode (Fdt, Node)) {
    Type = FdtGetProp (Fdt, Node, "device_type", &Length);
    if ((Type == NULL) || (Length != 7) || (CompareMem (Type, "memory", 7) != 0)) continue;
    Status = CollectReg (Fdt, Node, AddressCells, SizeCells, Banks, &BankCount, TRUE);
    if (EFI_ERROR (Status)) return Status;
  }
  if (BankCount == 0) return EFI_NOT_FOUND;
  for (Index = 0; Index < BankCount; Index++) {
    if (Banks[Index].End - Banks[Index].Base > MAX_UINT64 - TotalRam) return EFI_COMPROMISED_DATA;
    TotalRam += Banks[Index].End - Banks[Index].Base;
    for (Other = 0; Other < Index; Other++) {
      if ((Banks[Index].Base < Banks[Other].End) && (Banks[Other].Base < Banks[Index].End)) {
        return EFI_COMPROMISED_DATA;
      }
    }
  }
  if (TotalRam < A32_MAX_RAM_BYTES) {
    DEBUG ((DEBUG_ERROR, "A32MMU: FDT exposes only %lu MiB RAM; refusing static fallback\n", TotalRam / SIZE_1MB));
    return EFI_UNSUPPORTED;
  }

  Reserved = FdtPathOffset (Fdt, "/reserved-memory");
  if (Reserved >= 0) {
    ResAddress = (UINT32)FdtAddressCells (Fdt, Reserved);
    ResSize = (UINT32)FdtSizeCells (Fdt, Reserved);
    if (((ResAddress != 1) && (ResAddress != 2)) || ((ResSize != 1) && (ResSize != 2))) return EFI_COMPROMISED_DATA;
    for (Node = FdtFirstSubnode (Fdt, Reserved); Node >= 0; Node = FdtNextSubnode (Fdt, Node)) {
      CONST VOID *DynamicSize = FdtGetProp (Fdt, Node, "size", &Length);
      CONST VOID *Reg = FdtGetProp (Fdt, Node, "reg", &Length);
      if (Reg != NULL) {
        Status = CollectReg (Fdt, Node, ResAddress, ResSize, ReservedRanges, &ReservedCount, TRUE);
        if (EFI_ERROR (Status)) return Status;
      } else if (DynamicSize != NULL) {
        DEBUG ((DEBUG_ERROR, "A32MMU: dynamic reservation remains a Linux allocation request\n"));
      }
    }
  }

  ReserveCount = FdtGetNumberOfReserveMapEntries (Fdt);
  if (ReserveCount < 0) return EFI_COMPROMISED_DATA;
  for (ReserveIndex = 0; ReserveIndex < ReserveCount; ReserveIndex++) {
    UINT64 ReserveBase, ReserveSize;
    if (FdtGetReserveMapEntry (Fdt, ReserveIndex, &ReserveBase, &ReserveSize) != 0) return EFI_COMPROMISED_DATA;
    if ((ReserveSize == 0) || (ReserveBase + ReserveSize <= ReserveBase) || (ReservedCount >= A32_MAX_RANGES)) return EFI_COMPROMISED_DATA;
    ReservedRanges[ReservedCount].Base = ReserveBase;
    ReservedRanges[ReservedCount++].End = ReserveBase + ReserveSize;
  }

  Size = FdtTotalSize (Fdt);
  if ((Size < sizeof (FDT_HEADER)) || (Size > (16 * SIZE_1MB))) return EFI_COMPROMISED_DATA;
  Base = (UINT64)(UINTN)Fdt;
  if ((Size == 0) || (Base + Size <= Base) || (ReservedCount >= A32_MAX_RANGES)) return EFI_COMPROMISED_DATA;
  ReservedRanges[ReservedCount].Base = Base;
  ReservedRanges[ReservedCount++].End = Base + Size;

  Chosen = FdtPathOffset (Fdt, "/chosen");
  if (Chosen >= 0) {
    StartProp = FdtGetProp (Fdt, Chosen, "linux,initrd-start", &StartLength);
    EndProp = FdtGetProp (Fdt, Chosen, "linux,initrd-end", &EndLength);
    if ((StartProp != NULL) && (EndProp != NULL) &&
        (((StartLength == 4) || (StartLength == 8))) && (((EndLength == 4) || (EndLength == 8)))) {
      Start = ReadCells (StartProp, StartLength / 4);
      End = ReadCells (EndProp, EndLength / 4);
      if (End > Start) {
        if (ReservedCount >= A32_MAX_RANGES) return EFI_OUT_OF_RESOURCES;
        ReservedRanges[ReservedCount].Base = Start;
        ReservedRanges[ReservedCount++].End = End;
      }
    }

    HighProp = FdtGetProp (Fdt, Chosen, "atag,videolfb-fb_base_h", &HighLength);
    LowProp = FdtGetProp (Fdt, Chosen, "atag,videolfb-fb_base_l", &LowLength);
    FbSizeProp = FdtGetProp (Fdt, Chosen, "atag,videolfb-vramSize", &FbSizeLength);
    if ((HighProp != NULL) && (LowProp != NULL) && (FbSizeProp != NULL) &&
        (HighLength == 4) && (LowLength == 4) && (FbSizeLength == 4)) {
      FbBase = ((UINT64)Fdt32ToCpu (ReadUnaligned32 (HighProp)) << 32) | Fdt32ToCpu (ReadUnaligned32 (LowProp));
      FbSize = Fdt32ToCpu (ReadUnaligned32 (FbSizeProp));
      if ((FbSize == 0) || (FbBase + FbSize <= FbBase) || (ReservedCount >= A32_MAX_RANGES)) return EFI_COMPROMISED_DATA;
      for (Index = 0; Index < BankCount; Index++) {
        if ((FbBase >= Banks[Index].Base) && (FbBase + FbSize <= Banks[Index].End)) {
          FbPresent = TRUE;
          break;
        }
      }
      if (!FbPresent) return EFI_COMPROMISED_DATA;
      ReservedRanges[ReservedCount].Base = FbBase;
      ReservedRanges[ReservedCount++].End = FbBase + FbSize;
    }
  }

  // Excluding bootstrap regions from later RAM pieces does not validate the
  // fixed descriptors themselves. Reject conflicts before publishing any map.
  for (Index = 0; Index < ARRAY_SIZE (gMemoryDescriptor); Index++) {
    if (gMemoryDescriptor[Index].ResourceType == SYS_MEM &&
        !BootstrapRangeAllowed (gMemoryDescriptor[Index].Address,
                                gMemoryDescriptor[Index].Length,
                                Banks, BankCount, ReservedRanges, ReservedCount)) {
      DEBUG ((DEBUG_ERROR, "A32MMU: bootstrap region %a conflicts with live memory\n",
              gMemoryDescriptor[Index].Name));
      return EFI_COMPROMISED_DATA;
    }
  }
  Count = (UINT8)ARRAY_SIZE (gMemoryDescriptor);
  CopyMem (gFdtMemoryDescriptor, gMemoryDescriptor, sizeof (gMemoryDescriptor));
  if (FbPresent) {
    if (Count >= MAX_ARM_MEMORY_REGION_DESCRIPTOR_COUNT) return EFI_OUT_OF_RESOURCES;
    AsciiSPrint (gFdtMemoryDescriptor[Count].Name, MAX_MEMORY_REGION_NAME_LENGTH, "Display Reserved");
    gFdtMemoryDescriptor[Count].Address = FbBase;
    gFdtMemoryDescriptor[Count].Length = FbSize;
    gFdtMemoryDescriptor[Count].HobOption = AddMem;
    gFdtMemoryDescriptor[Count].ResourceType = MEM_RES;
    gFdtMemoryDescriptor[Count].ResourceAttribute = SYS_MEM_CAP;
    gFdtMemoryDescriptor[Count].MemoryType = Reserv;
    gFdtMemoryDescriptor[Count].ArmAttributes = WRITE_THROUGH_XN;
    Count++;
  }
  for (Index = 0; Index < ARRAY_SIZE (gMemoryDescriptor); Index++) {
    if (gMemoryDescriptor[Index].ResourceType == SYS_MEM) {
      if (ReservedCount >= A32_MAX_RANGES) return EFI_OUT_OF_RESOURCES;
      ReservedRanges[ReservedCount].Base = gMemoryDescriptor[Index].Address;
      ReservedRanges[ReservedCount++].End = gMemoryDescriptor[Index].Address + gMemoryDescriptor[Index].Length;
    }
  }

  Added = 0;
  for (Index = 0; Index < BankCount; Index++) {
    Pieces[0] = Banks[Index];
    PieceCount = 1;
    for (Other = 0; Other < ReservedCount; Other++) {
      Status = SubtractRange (Pieces, &PieceCount, ReservedRanges[Other]);
      if (EFI_ERROR (Status)) return Status;
    }
    for (Other = 0; Other < PieceCount; Other++) {
      if (Pieces[Other].Base > MAX_UINT64 - A32_PAGE_MASK) return EFI_COMPROMISED_DATA;
      Base = (Pieces[Other].Base + A32_PAGE_MASK) & ~A32_PAGE_MASK;
      End = Pieces[Other].End & ~A32_PAGE_MASK;
      if ((End <= Base) || (End - Base < A32_MIN_PIECE_BYTES)) continue;
      if (Count >= MAX_ARM_MEMORY_REGION_DESCRIPTOR_COUNT) return EFI_OUT_OF_RESOURCES;
      AsciiSPrint (gFdtMemoryDescriptor[Count].Name, MAX_MEMORY_REGION_NAME_LENGTH, "LK RAM %u", (UINT32)Added);
      gFdtMemoryDescriptor[Count].Address = Base;
      gFdtMemoryDescriptor[Count].Length = End - Base;
      gFdtMemoryDescriptor[Count].HobOption = AddMem;
      gFdtMemoryDescriptor[Count].ResourceType = SYS_MEM;
      gFdtMemoryDescriptor[Count].ResourceAttribute = SYS_MEM_CAP;
      gFdtMemoryDescriptor[Count].MemoryType = Conv;
      gFdtMemoryDescriptor[Count].ArmAttributes = WRITE_BACK;
      UsableRam += End - Base;
      Count++;
      Added++;
    }
  }
  if (UsableRam < A32_MAX_RAM_BYTES) {
    DEBUG ((DEBUG_ERROR, "A32MMU: only %lu MiB RAM remains after reservations\n", UsableRam / SIZE_1MB));
    return EFI_UNSUPPORTED;
  }
  Status = A32PublishMemoryMap (gFdtMemoryDescriptor, Count);
  if (EFI_ERROR (Status)) return Status;
  gFdtMemoryDescriptorCount = Count;
  *MemoryDescriptor = gFdtMemoryDescriptor;
  *MemoryDescriptorCount = Count;
  DEBUG ((DEBUG_ERROR, "A32MMU: FDT RAM=%lu MiB usable=%lu MiB regions=%u\n",
          TotalRam / SIZE_1MB, UsableRam / SIZE_1MB, Count));
  return EFI_SUCCESS;
}

VOID GetMemoryMap (
  OUT EFI_MEMORY_REGION_DESCRIPTOR **MemoryDescriptor,
  OUT UINT8 *MemoryDescriptorCount)
{
  if (gFdtMemoryDescriptorCount != 0) {
    *MemoryDescriptor = gFdtMemoryDescriptor;
    *MemoryDescriptorCount = gFdtMemoryDescriptorCount;
    return;
  }
  *MemoryDescriptor = gMemoryDescriptor;
  *MemoryDescriptorCount = ARRAY_SIZE (gMemoryDescriptor);
}
