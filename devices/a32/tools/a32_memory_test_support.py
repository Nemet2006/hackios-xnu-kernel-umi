"""Host compilation support: production C, firmware/FDT boundaries replaced only."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
PKG = ROOT / 'devices/a32/uefi/files/Platforms/Samsung/a32Pkg'
SILICON = ROOT / 'out/a32/reference-uefi-merlinx/Silicon/Silicium/SiliciumPkg'


def without_includes(text):
    return re.sub(r'^#include .*$', '', text, flags=re.M)


PRELUDE = r'''
#ifndef TEST_SUPPORT_H
#define TEST_SUPPORT_H
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#include <stdlib.h>
#define IN
#define OUT
#define CONST const
#define STATIC static
#define VOID void
#define EFIAPI
#define TRUE 1
#define FALSE 0
#define MAX_UINT64 UINT64_MAX
#define MAX_UINT32 UINT32_MAX
#define MAX_UINT16 UINT16_MAX
#define MAX_UINTN SIZE_MAX
#define SIZE_1GB 0x40000000ULL
#define SIZE_512MB 0x20000000ULL
#define SIZE_16MB 0x1000000ULL
#define SIZE_1MB 0x100000ULL
#define SIZE_4KB 0x1000ULL
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define EFI_SUCCESS 0
#define EFI_INVALID_PARAMETER 2
#define EFI_UNSUPPORTED 3
#define EFI_OUT_OF_RESOURCES 9
#define EFI_NOT_FOUND 14
#define EFI_ALREADY_STARTED 20
#define EFI_COMPROMISED_DATA 33
#define EFI_ERROR(s) ((s)!=EFI_SUCCESS)
#define DEBUG_ERROR 1
#define DEBUG(x) (++debug_calls)
#define CopyMem memmove
#define ZeroMem(p,n) memset(p,0,n)
#define CompareMem memcmp
#define AsciiStrCmp strcmp
#define AsciiStriCmp strcasecmp
#define AsciiSPrint snprintf
#define STATIC_ASSERT(c,m) _Static_assert(c,m)
typedef uint8_t UINT8;
typedef uint16_t UINT16;
typedef uint32_t UINT32;
typedef uint64_t UINT64, EFI_STATUS, EFI_PHYSICAL_ADDRESS, EFI_RESOURCE_ATTRIBUTE_TYPE;
typedef uint32_t EFI_RESOURCE_TYPE;
typedef int EFI_MEMORY_TYPE, ARM_MEMORY_REGION_ATTRIBUTES;
typedef size_t UINTN;
typedef intptr_t INTN;
typedef int32_t INT32;
typedef char CHAR8;
typedef int BOOLEAN;
typedef struct {UINT32 a; UINT16 b,c; UINT8 d[8];} EFI_GUID;
typedef struct {UINT16 HobType,HobLength;UINT32 Reserved;} EFI_HOB_GENERIC_HEADER;
typedef struct {EFI_HOB_GENERIC_HEADER Header; EFI_GUID Name;} EFI_HOB_GUID_TYPE;
#define GET_GUID_HOB_DATA(h) ((void *)((EFI_HOB_GUID_TYPE *)(h)+1))
#define GET_GUID_HOB_DATA_SIZE(h) (((EFI_HOB_GUID_TYPE *)(h))->Header.HobLength-sizeof(EFI_HOB_GUID_TYPE))
#define GET_HOB_LENGTH(h) (((EFI_HOB_GENERIC_HEADER *)(h))->HobLength)
#define MAX_ARM_MEMORY_REGION_DESCRIPTOR_COUNT 128
#define MAX_MEMORY_REGION_NAME_LENGTH 32
typedef enum {NoHob,AddMem,AddDev,HobOnlyNoCacheSetting,AllocOnly,MaxMem} EFI_MEMORY_HOB_OPTION;
typedef struct {
 CHAR8 Name[32]; EFI_PHYSICAL_ADDRESS Address; UINT64 Length;
 EFI_MEMORY_HOB_OPTION HobOption; EFI_RESOURCE_TYPE ResourceType;
 EFI_RESOURCE_ATTRIBUTE_TYPE ResourceAttribute; EFI_MEMORY_TYPE MemoryType;
 ARM_MEMORY_REGION_ATTRIBUTES ArmAttributes;
} EFI_MEMORY_REGION_DESCRIPTOR;
#define SYS_MEM 0
#define MEM_RES 5
#define MMAP_IO 1
#define SYS_MEM_CAP 0x3c07
#define UNCACHEABLE 0x400
#define BsData 4
#define Conv 7
#define Reserv 0
#define MmIO 11
#define WRITE_BACK 1
#define WRITE_THROUGH_XN 2
#define NS_DEVICE 4
typedef struct {UINT32 fields[10];} FDT_HEADER;
extern int header_calls,traversal_calls,header_result,debug_calls;
extern UINT32 fixture_size;
extern UINT64 fixture_reserve_size;
extern int fixture_valid, allocation_fail, hob_builds;
extern EFI_GUID gA32MemoryMapHobGuid;
extern UINT8 hob_store[16384];
extern int hob_present;
int FdtCheckHeader(const void *);
UINT32 FdtTotalSize(const void *);
INT32 FdtPathOffset(const void *,const char *);
INT32 FdtAddressCells(const void *,INT32);
INT32 FdtSizeCells(const void *,INT32);
INT32 FdtFirstSubnode(const void *,INT32);
INT32 FdtNextSubnode(const void *,INT32);
const void *FdtGetProp(const void *,INT32,const char *,INT32 *);
INTN FdtGetNumberOfReserveMapEntries(const void *);
int FdtGetReserveMapEntry(const void *,INTN,UINT64 *,UINT64 *);
static inline UINT64 ReadUnaligned64(const void *p) {UINT64 v;memcpy(&v,p,8);return v;}
static inline UINT32 ReadUnaligned32(const void *p) {UINT32 v;memcpy(&v,p,4);return v;}
#define Fdt64ToCpu __builtin_bswap64
#define Fdt32ToCpu __builtin_bswap32
void *GetFirstGuidHob(const EFI_GUID *);
void *BuildGuidHob(const EFI_GUID *,UINTN);
EFI_STATUS GetMemoryMapFromFdt(const void *,EFI_MEMORY_REGION_DESCRIPTOR **,UINT8 *);
void SecGetMemoryMap(EFI_MEMORY_REGION_DESCRIPTOR **,UINT8 *);
void DxeGetMemoryMap(EFI_MEMORY_REGION_DESCRIPTOR **,UINT8 *);
EFI_STATUS LocateMemoryRegionByName(CHAR8 *,EFI_MEMORY_REGION_DESCRIPTOR *);
#endif
'''

STUBS = r'''
int header_calls,traversal_calls,header_result,debug_calls;
UINT32 fixture_size=4096;
UINT64 fixture_reserve_size;
int fixture_valid,allocation_fail,hob_builds,hob_present;
EFI_GUID gA32MemoryMapHobGuid={0};
_Alignas(8) UINT8 hob_store[16384];
int FdtCheckHeader(const void *f) {(void)f;header_calls++;return header_result;}
UINT32 FdtTotalSize(const void *f) {(void)f;return fixture_size;}
INT32 FdtPathOffset(const void *f,const char *p) {
 (void)f;traversal_calls++;
 if(!fixture_valid) return -1;
 if(!strcmp(p,"/")) return 0;
 if(!strcmp(p,"/chosen")) return 2;
 return -1;
}
INT32 FdtAddressCells(const void *f,INT32 n) {(void)f;(void)n;return 2;}
INT32 FdtSizeCells(const void *f,INT32 n) {(void)f;(void)n;return 2;}
INT32 FdtFirstSubnode(const void *f,INT32 n) {(void)f;return n==0?1:-1;}
INT32 FdtNextSubnode(const void *f,INT32 n) {(void)f;(void)n;return -1;}
const void *FdtGetProp(const void *f,INT32 n,const char *p,INT32 *len) {
 (void)f;
 static const UINT8 reg[]={0,0,0,0,0x40,0,0,0,0,0,0,1,0,0,0,0};
 static const UINT8 hi[]={0,0,0,0},lo[]={0x80,0,0,0},sz[]={1,0,0,0};
 if(n==1 && !strcmp(p,"device_type")){*len=7;return "memory";}
 if(n==1 && !strcmp(p,"reg")){*len=16;return reg;}
 if(n==2){
  *len=4;
  if(!strcmp(p,"atag,videolfb-fb_base_h")) return hi;
  if(!strcmp(p,"atag,videolfb-fb_base_l")) return lo;
  if(!strcmp(p,"atag,videolfb-vramSize")) return sz;
 }
 *len=-1;return NULL;
}
INTN FdtGetNumberOfReserveMapEntries(const void *f) {(void)f;return fixture_reserve_size?1:0;}
int FdtGetReserveMapEntry(const void *f,INTN i,UINT64 *b,UINT64 *s) {
 (void)f;assert(i==0 && fixture_reserve_size);*b=0x90000000;*s=fixture_reserve_size;return 0;
}
void *GetFirstGuidHob(const EFI_GUID *g) {assert(g==&gA32MemoryMapHobGuid);return hob_present?hob_store:NULL;}
void *BuildGuidHob(const EFI_GUID *g,UINTN n) {
 assert(g==&gA32MemoryMapHobGuid);hob_builds++;
 if(allocation_fail)return NULL;
 assert(!hob_present && n+24<=sizeof(hob_store));
 EFI_HOB_GUID_TYPE *h=(void *)hob_store;
 memset(hob_store,0,sizeof(hob_store));h->Header.HobLength=(UINT16)((n+24+7)&~7ULL);
 h->Name=*g;hob_present=1;return h+1;
}
'''


def compile_test(directory, main, sources, extra='', stubs=STUBS, extra_sources=(),
                 include_dirs=(), sanitize=True):
    """Strip platform includes only; compile each production source separately.

    `stubs` replaces the default FDT/HOB boundary implementation.  `extra_sources`
    and `include_dirs` let a test use a real dependency (for example the libfdt
    copy that the firmware already builds) instead of hand-written fakes.
    """
    directory = Path(directory)
    header = PKG / 'Include/Guid/A32MemoryMapHob.h'
    common = PRELUDE + (without_includes(header.read_text()) if header.exists() else '')
    (directory / 'support.h').write_text(common)
    units = []
    for index, (path, defines) in enumerate(sources):
        unit = directory / f'production{index}.c'
        unit.write_text('#include "support.h"\n' + defines + '\n' + without_includes(path.read_text()))
        units.append(str(unit))
    units.extend(str(Path(path)) for path in extra_sources)
    (directory / 'main.c').write_text('#include "support.h"\n' + stubs + extra + main)
    binary = directory / 'test'
    flags = ['-fsanitize=undefined', '-fno-sanitize-recover=all'] if sanitize else []
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', *flags,
                    *[f'-I{path}' for path in include_dirs],
                    *units, str(directory/'main.c'), '-o', str(binary)], check=True)
    return binary
