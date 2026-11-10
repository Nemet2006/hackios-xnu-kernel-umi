#!/usr/bin/env python3
"""Catch traversal before size validation in the production FDT parser."""
import subprocess
import tempfile
from a32_memory_test_support import PKG, compile_test

main = r'''
int main(void) {
 const UINT64 invalid[]={0,0x40000001,0x3ffffff8,0x13fffffe0,UINT64_MAX-7};
 EFI_MEMORY_REGION_DESCRIPTOR *map;UINT8 count;
 for(UINTN i=0;i<ARRAY_SIZE(invalid);i++) {
  map=(void *)1;count=99;header_calls=traversal_calls=0;
  assert(GetMemoryMapFromFdt((void *)(UINTN)invalid[i],&map,&count)==EFI_INVALID_PARAMETER);
  assert(!map && !count && !header_calls && !traversal_calls);
 }
 const UINT32 sizes[]={0,39,0x1000001,4096};
 for(UINTN i=0;i<ARRAY_SIZE(sizes);i++) {
  fixture_size=sizes[i];header_calls=traversal_calls=0;
  const void *address=(void *)(UINTN)(i==3?0x13ffff000ULL+8:0x4bc80000ULL);
  assert(GetMemoryMapFromFdt(address,&map,&count)==EFI_COMPROMISED_DATA);
  assert(!map && !count && header_calls==1 && !traversal_calls);
 }
 header_result=-1;fixture_size=4096;header_calls=traversal_calls=0;
 assert(GetMemoryMapFromFdt((void *)0x4bc80000,&map,&count)==EFI_INVALID_PARAMETER);
 assert(header_calls==1 && !traversal_calls && !map && !count);
 header_result=0;fixture_size=40;
 assert(GetMemoryMapFromFdt((void *)0x4bc80000,&map,&count)==EFI_COMPROMISED_DATA);
 assert(traversal_calls==1); /* valid bounds reach stubbed traversal */
 puts("PASS: 11 FDT entry cases; invalid bounds never traverse");
}
'''
with tempfile.TemporaryDirectory(prefix='a32-fdt-entry-') as directory:
    sources = [(PKG/'Library/MemoryMapLib/MemoryMapLib.c', '#define GetMemoryMap SecGetMemoryMap')]
    common = PKG/'Library/MemoryMapLib/A32MemoryMapHob.c'
    if common.exists():
        sources.append((common, ''))
    subprocess.run([str(compile_test(directory, main, sources))], check=True)
