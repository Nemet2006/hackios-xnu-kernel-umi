#!/usr/bin/env python3
"""Exercise production HOB validation and (as added) separate SEC/DXE state."""
import subprocess
import tempfile
from a32_memory_test_support import PKG, SILICON, compile_test

validator_tests = r'''
typedef struct {
 A32_MEMORY_MAP_HOB_HEADER h;
 EFI_MEMORY_REGION_DESCRIPTOR entries[128];
 UINT8 padding[8];
} FIXTURE;
static FIXTURE fixture;
static EFI_MEMORY_REGION_DESCRIPTOR output[128],sentinel[128];
static void init_fixture(UINT32 count) {
 memset(&fixture,0,sizeof(fixture));
 fixture.h=(A32_MEMORY_MAP_HOB_HEADER){1,count,sizeof(fixture.entries[0]),0};
 for(UINT32 i=0;i<128;i++) {
  strcpy(fixture.entries[i].Name,"Display Reserved");
  fixture.entries[i].Address=0x80000000ULL+i*0x1000000ULL;
  fixture.entries[i].Length=0x1000000;
  fixture.entries[i].HobOption=AddMem;fixture.entries[i].ResourceType=MEM_RES;
  fixture.entries[i].MemoryType=Reserv;
 }
 memset(output,0xa5,sizeof(output));memcpy(sentinel,output,sizeof(output));
}
static void reject(const void *data,UINTN size,UINTN capacity) {
 UINT8 count=99;
 assert(EFI_ERROR(A32CopyMemoryMapHob(data,size,output,capacity,&count)));
 assert(count==0 && !memcmp(output,sentinel,sizeof(output)));
}
static void validator_test(void) {
 const UINTN one=16+sizeof(fixture.entries[0]);UINT8 count;
 for(UINT32 n=1;n<=128;n+=127) {
  init_fixture(n);
  assert(A32CopyMemoryMapHob(&fixture,16+n*sizeof(output[0]),output,128,&count)==EFI_SUCCESS);
  assert(count==n && !memcmp(output,fixture.entries,n*sizeof(output[0])));
 }
 init_fixture(1);
 for(UINTN n=0;n<one;n++)reject(&fixture,n,128);
 reject(NULL,one,128);reject(&fixture,SIZE_MAX,128);
 reject(&fixture,one+8,128);reject(&fixture,one,0);
 /* This AARCH64 ABI has no payload padding; even one extra byte is invalid. */
 reject(&fixture,one+1,128);
 const UINT32 bad_counts[]={0,129,UINT32_MAX};
 for(UINTN i=0;i<ARRAY_SIZE(bad_counts);i++){fixture.h.DescriptorCount=bad_counts[i];reject(&fixture,one,128);}
 init_fixture(1);fixture.h.Version=2;reject(&fixture,one,128);
 init_fixture(1);fixture.h.DescriptorSize--;reject(&fixture,one,128);
 init_fixture(1);fixture.h.Reserved=1;reject(&fixture,one,128);
 init_fixture(1);memset(fixture.entries[0].Name,'x',32);reject(&fixture,one,128);
 init_fixture(1);fixture.entries[0].Length=0;reject(&fixture,one,128);
 init_fixture(1);fixture.entries[0].Address=UINT64_MAX-15;fixture.entries[0].Length=16;reject(&fixture,one,128);
 init_fixture(2);fixture.entries[1].Length=0;reject(&fixture,16+2*sizeof(output[0]),128);
 init_fixture(1);
 UINT8 unaligned[sizeof(fixture)+1];memcpy(unaligned+1,&fixture,one);
 assert(A32CopyMemoryMapHob(unaligned+1,one,output,128,&count)==EFI_SUCCESS);
 assert(count==1 && output[0].Address==0x80000000);
 count=99;assert(A32CopyMemoryMapHob(&fixture,one,NULL,128,&count)==EFI_INVALID_PARAMETER && count==0);
 assert(A32CopyMemoryMapHob(&fixture,one,output,128,NULL)==EFI_INVALID_PARAMETER);
 puts("PASS: HOB round-trip, all short lengths, metadata, bounds, atomic copy and unaligned input");
}
'''

producer_tests = r'''
static int has_display(EFI_MEMORY_REGION_DESCRIPTOR *map,UINT8 count) {
 for(UINT8 i=0;i<count;i++)if(!strcmp(map[i].Name,"Display Reserved"))return 1;
 return 0;
}
static void producer_test(int scenario) {
 EFI_MEMORY_REGION_DESCRIPTOR *map=(void *)1;UINT8 count=99;
 SecGetMemoryMap(&map,&count);assert(map && count && !has_display(map,count));
 fixture_valid=1;
 if(scenario==1) {
  init_fixture(1);
  assert(A32PublishMemoryMap(NULL,1)==EFI_INVALID_PARAMETER && hob_builds==0);
  fixture.entries[0].Length=0;
  assert(EFI_ERROR(A32PublishMemoryMap(fixture.entries,1)) && hob_builds==0);
  init_fixture(1);
  assert(A32PublishMemoryMap(fixture.entries,0)==EFI_INVALID_PARAMETER && hob_builds==0);
  assert(A32PublishMemoryMap(fixture.entries,129)==EFI_INVALID_PARAMETER && hob_builds==0);
  assert(A32PublishMemoryMap(fixture.entries,1)==EFI_SUCCESS && hob_builds==1);
  assert(A32PublishMemoryMap(fixture.entries,1)==EFI_ALREADY_STARTED && hob_builds==1);
  assert(A32CopyMemoryMapHob(GET_GUID_HOB_DATA(hob_store),GET_GUID_HOB_DATA_SIZE(hob_store),output,128,&count)==EFI_SUCCESS);
  assert(count==1 && output[0].Address==0x80000000);
 } else if(scenario==2) {
  allocation_fail=1;
  assert(GetMemoryMapFromFdt((void *)0x4bc80000,&map,&count)==EFI_OUT_OF_RESOURCES);
  assert(!map && !count && !hob_present && hob_builds==1);
  SecGetMemoryMap(&map,&count);assert(!has_display(map,count));
 } else if(scenario==3) {
  /* Fail late, after the descriptor array was populated. */
  fixture_reserve_size=0x80000000;
  assert(GetMemoryMapFromFdt((void *)0x4bc80000,&map,&count)==EFI_UNSUPPORTED);
  assert(!map && !count && !hob_present && !hob_builds);
  SecGetMemoryMap(&map,&count);assert(!has_display(map,count));
 } else {
  assert(GetMemoryMapFromFdt((void *)0x4bc80000,&map,&count)==EFI_SUCCESS);
  assert(has_display(map,count) && hob_builds==1);
  EFI_MEMORY_REGION_DESCRIPTOR *local;UINT8 local_count;
  SecGetMemoryMap(&local,&local_count);
  assert(local==map && local_count==count && has_display(local,local_count));
  if(scenario==4) {
   assert(GetMemoryMapFromFdt((void *)0x4bc80000,&map,&count)==EFI_ALREADY_STARTED);
  } else {
   assert(GetMemoryMapFromFdt(NULL,&map,&count)==EFI_INVALID_PARAMETER);
  }
  assert(!map && !count && hob_builds==1);
  SecGetMemoryMap(&local,&local_count);assert(!has_display(local,local_count));
 }
 puts("PASS: SEC publication/state scenario");
}
'''

consumer_tests = r'''
static void consumer_test(int scenario) {
 EFI_MEMORY_REGION_DESCRIPTOR *map=(void *)1,found;UINT8 count=99;
 int debug_before=debug_calls;
 DxeGetMemoryMap(&map,&count);assert(!map && !count && debug_calls==debug_before);
 assert(LocateMemoryRegionByName("Display Reserved",&found)==EFI_NOT_FOUND);
 fixture_valid=1;
 assert(GetMemoryMapFromFdt((void *)0x4bc80000,&map,&count)==EFI_SUCCESS);
 EFI_MEMORY_REGION_DESCRIPTOR *sec=map;UINT8 sec_count=count;
 EFI_HOB_GUID_TYPE *hob=(void *)hob_store;
 A32_MEMORY_MAP_HOB_HEADER *header=GET_GUID_HOB_DATA(hob);
 if(scenario==6)header->Version=2;
 if(scenario==7)hob->Header.HobLength=8; /* reject before GUID data size underflow */
 if(scenario==8)hob->Header.HobLength--;
 debug_before=debug_calls;
 DxeGetMemoryMap(&map,&count);
 assert(debug_calls==debug_before);
 if(scenario<=8) {
  assert(!map && !count);
  assert(LocateMemoryRegionByName("Display Reserved",&found)==EFI_NOT_FOUND);
 } else {
  assert(map!=sec && count==sec_count && !memcmp(map,sec,count*sizeof(*map)));
  assert(LocateMemoryRegionByName("Display Reserved",&found)==EFI_SUCCESS);
  assert(found.Address==0x80000000 && found.Length==0x1000000);
  /* Neither producer globals nor the original HOB own the DXE result. */
  memset(sec,0,sec_count*sizeof(*sec));memset(hob_store,0,sizeof(hob_store));hob_present=0;
  DxeGetMemoryMap(&map,&count);
  assert(count==sec_count && has_display(map,count));
  assert(LocateMemoryRegionByName("Display Reserved",&found)==EFI_SUCCESS);
  assert(found.Address==0x80000000 && found.Length==0x1000000);
 }
 assert(debug_calls==debug_before);
 puts("PASS: independent DXE state, lookup, lifetime or malformed HOB scenario");
}
'''

with tempfile.TemporaryDirectory(prefix='a32-handoff-') as directory:
    source = PKG/'Library/MemoryMapLib/A32MemoryMapHob.c'
    assert source.exists(), 'Missing production A32CopyMemoryMapHob implementation'
    main = validator_tests + producer_tests + consumer_tests + r'''
int main(int argc,char **argv){
 if(argc==1)validator_test();else if(atoi(argv[1])<6)producer_test(atoi(argv[1]));else consumer_test(atoi(argv[1]));
}
'''
    consumer = PKG/'Library/MemoryMapDxeLib/MemoryMapDxeLib.c'
    assert consumer.exists(), 'Missing production DXE HOB consumer'
    binary = compile_test(directory, main, [(source, ''),
        (PKG/'Library/MemoryMapLib/MemoryMapLib.c', '#define GetMemoryMap SecGetMemoryMap'),
        (consumer, '#define GetMemoryMap DxeGetMemoryMap'),
        (SILICON/'Library/MemoryMapHelperLib/MemoryMapHelper.c', '#define GetMemoryMap DxeGetMemoryMap')])
    for args in [[]] + [[str(i)] for i in range(1,10)]:
        subprocess.run([str(binary), *args], check=True)
