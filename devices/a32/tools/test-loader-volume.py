#!/usr/bin/env python3
"""Run production volume-loading functions with host EFI stubs and guarded RAM.

This tests allocation/file ownership, not ARM execution or actual firmware.
"""
import os
import importlib.util
import struct
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
source = (ROOT / "xnuloader/loader.c").read_text()


def section(start, end):
    return source[source.index(start):source.index(end, source.index(start))]


code = r'''
#define _GNU_SOURCE
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <sys/mman.h>
#include "efi.h"
#define PAYLOAD_MAX_SIZE 0x04000000ULL
#define PAYLOAD_MAGIC 0x50554e58u
static void *region;
#define PAYLOAD_BASE ((uintptr_t)region)
struct payload_header { uint32_t magic,size; };
struct payload_entry { char name[16]; uint32_t size,reserved; };
static int payload_readable;
static efi_boot_services services, *BS = &services;
static efi_handle IMAGE;
static int str_eq(const char*a,const char*b) { return strcmp(a,b)==0; }
'''
code += section("static uint64_t\npayload_walk_size(", "static int\nparse_payload(")
code += section("static uint64_t volume_payload_bytes;", "/*\n * The version of the kernel")
code += section("static const char *\npayload_text_entry(", "/*\n * The greeting.")
code += r'''
static efi_file root, file;
static efi_simple_fs fs;
static efi_loaded_image loaded;
static unsigned char builtin_fixture[72], *fixture = builtin_fixture;
static size_t fixture_size = sizeof(builtin_fixture);
static int mode, allocated, freed, reads, closes;
static uint64_t offset;
static efi_status close_file(efi_file *f) { (void)f; closes++; return 0; }
static efi_status open_file(efi_file *r,efi_file **f,const char16 *n,uint64_t m,uint64_t a) {
 (void)r;(void)n;(void)m;(void)a;
 if(mode==2) return EFI_ERROR_BIT|14;
 *f=&file;return 0;
}
static efi_status open_volume(efi_simple_fs *s,efi_file **r) {(void)s;*r=&root;return 0;}
static efi_status protocol(efi_handle h,const efi_guid *g,void **out) {
 (void)h; efi_guid image_guid=EFI_LOADED_IMAGE_GUID;
 *out=memcmp(g,&image_guid,sizeof(*g))==0?(void*)&loaded:(void*)&fs; return 0;
}
static efi_status info(efi_file *f,const efi_guid*g,uint64_t*n,void*b) {
 (void)f;(void)g;
 if(mode==3) {*n=0;return 0;}
 uint64_t size=fixture_size;memcpy((char*)b+EFI_FILE_INFO_FILE_SIZE_OFFSET,&size,8);
 *n=EFI_FILE_INFO_FILE_SIZE_OFFSET+8;return 0;
}
static efi_status alloc(int t,int m,uint64_t pages,uint64_t *address) {
 assert(t==2 && m==2 && pages==PAYLOAD_MAX_SIZE/4096 && *address==PAYLOAD_BASE);
 if(mode==1) return EFI_ERROR_BIT|9;
 assert(mprotect(region,PAYLOAD_MAX_SIZE,PROT_READ|PROT_WRITE)==0);
 allocated++;return 0;
}
static efi_status release(uint64_t address,uint64_t pages) {
 assert(address==PAYLOAD_BASE && pages==PAYLOAD_MAX_SIZE/4096 && allocated==1 && !freed);
 freed++;assert(mprotect(region,PAYLOAD_MAX_SIZE,PROT_NONE)==0);return 0;
}
static efi_status read_file(efi_file*f,uint64_t*n,void*b) {
 (void)f; assert(allocated && !freed);reads++;
 if(mode==4 && reads==2) return EFI_ERROR_BIT|7;
 if(mode==5) {*n=0;return 0;}
 if(mode==6) {(*n)++;return 0;}
 if(*n>13) *n=13; /* successful reads may be shorter than requested */
 assert(offset+*n<=fixture_size);memcpy(b,fixture+offset,*n);offset+=*n;return 0;
}
int main(int argc, char **argv) {
 assert(argc==1 || argc==3);
 if(argc==3) {
  FILE *input=fopen(argv[1],"rb");assert(input);
  assert(fseek(input,0,SEEK_END)==0);long length=ftell(input);assert(length>=0);
  fixture_size=(size_t)length;fixture=malloc(fixture_size ? fixture_size : 1);assert(fixture);
  rewind(input);assert(fread(fixture,1,fixture_size,input)==fixture_size);assert(fclose(input)==0);
 }
 region=mmap(NULL,PAYLOAD_MAX_SIZE,PROT_NONE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
 assert(region!=MAP_FAILED);
 services.handle_protocol=protocol;services.allocate_pages=alloc;services.free_pages=release;
 loaded.device=(void*)1;fs.open_volume=open_volume;root.open=open_file;root.close=close_file;
 file.close=close_file;file.get_info=info;file.read=read_file;
 for(mode=0;mode<(argc==3?1:8);mode++) {
  if(argc==1) {
  memset(fixture,0,fixture_size);
  struct payload_header h={PAYLOAD_MAGIC,fixture_size-8};memcpy(fixture,&h,8);
  struct payload_entry e={"platform",4,0};memcpy(fixture+8,&e,24);memcpy(fixture+32,"a32",4);
  if(mode==7) fixture[4]++; /* declared file length mismatch */
  }
  allocated=freed=reads=closes=0;offset=0;payload_readable=0;
  assert(payload_text_entry("platform")==NULL); /* PROT_NONE before allocation */
  int ok=load_payload_from_volume();
  int expected=argc==3?atoi(argv[2]):mode==0;
  if(ok!=expected) {
   fprintf(stderr,"FAIL: volume load returned %d, expected %d for %s\n",ok,expected,argc==3?argv[1]:"built-in fixture");
   return 1;
  }
  assert(payload_readable==ok);
  if(ok) {
   const char *platform=payload_text_entry("platform");
   if(platform) assert(strcmp(platform,"a32")==0);
   assert(reads>1 && allocated==1 && !freed);release(PAYLOAD_BASE,PAYLOAD_MAX_SIZE/4096);
   payload_readable=0;
  } else {
   assert(volume_payload_bytes==0);
   assert(payload_text_entry("platform")==NULL); /* PROT_NONE after free/failure */
   assert(freed==allocated);
  }
  assert(closes==(mode==2?1:2));
 }
 assert(munmap(region,PAYLOAD_MAX_SIZE)==0);
 if(argc==3) free(fixture);
 else puts("PASS: 8 production volume-load scenarios with guarded RAM and close/free accounting");
}
'''


def payload(entries):
    body = b"".join(struct.pack("<16sII", name, len(value), 0) + value +
                    bytes(-len(value) % 16) for name, value in entries)
    body += bytes(24)
    return struct.pack("<II", 0x50554E58, len(body)) + body


base_entries = [(b"platform", b"a32\0"), (b"kernel", b"K")]
valid = payload(base_entries)
bad_name_tail = bytearray(valid)
bad_name_tail[8 + 9] = ord("x")  # hidden after platform's first NUL
bad_terminator = bytearray(valid)
bad_terminator[-23] = ord("x")
bad_padding = bytearray(valid)
bad_padding[36] = 1  # first padding byte following a32 NUL
cases = [
    ("canonical-a32", valid, True, True),
    ("nonzero-name-tail", bytes(bad_name_tail), False, False),
    ("nonzero-terminator-name", bytes(bad_terminator), False, False),
    ("non-ascii-entry-name", payload(base_entries + [(b"ext\xff", b"x")]), False, False),
    ("nonzero-data-padding", bytes(bad_padding), False, False),
    ("embedded-text-nul", payload(base_entries + [(b"cmdline", b"one\0two\0")]), False, False),
    ("empty-text", payload(base_entries + [(b"cmdline", b"\0")]), True, True),
    ("unknown-extension", payload(base_entries + [(b"future", b"\0\xffdata")]), True, True),
    ("aligned-binary", payload(base_entries + [(b"binary", bytes(range(16)))]), True, True),
    ("max-length-name", payload(base_entries + [(b"abcdefghijklmno", b"")]), True, True),
    ("unterminated-name", payload(base_entries + [(b"abcdefghijklmnop", b"x")]), False, False),
    ("unterminated-text", payload(base_entries + [(b"cmdline", b"abc")]), False, False),
    ("zero-length-text", payload(base_entries + [(b"cmdline", b"")]), False, False),
    ("empty-file", b"", False, False),
    ("short-header", b"XNUP", False, False),
    ("duplicate-known", payload(base_entries + [(b"kernel", b"other")]), False, False),
    ("duplicate-extension", payload(base_entries + [(b"future", b"a"), (b"future", b"b")]), False, False),
    ("128-unique-entries", payload(base_entries + [(f"ext{i}".encode(), b"") for i in range(126)]), True, True),
    ("129-unique-entries", payload(base_entries + [(f"ext{i}".encode(), b"") for i in range(127)]), False, False),
    ("generic-no-platform", payload([(b"kernel", b"K")]), False, True),
]
spec = importlib.util.spec_from_file_location("payload_verifier", ROOT / "devices/a32/tools/verify-payload.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)

with tempfile.TemporaryDirectory(prefix="a32-volume-test-") as directory:
    cfile = Path(directory) / "test.c"
    binary = Path(directory) / "test"
    cfile.write_text(code)
    subprocess.run([os.environ.get("CC", "cc"), "-std=c11", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=undefined", "-fno-sanitize-recover=all",
                    "-I", str(ROOT / "xnuloader"), str(cfile), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
    failures = []
    for name, data, host_ok, runtime_ok in cases:
        try:
            verifier.inspect(data)
            accepted = True
        except ValueError:
            accepted = False
        host_matches = accepted == host_ok
        if not host_matches:
            print(f"FAIL: {name}: host accepted={accepted}, expected={host_ok}", flush=True)
        fixture_path = Path(directory) / (name + ".xnup")
        fixture_path.write_bytes(data)
        result = subprocess.run([str(binary), str(fixture_path), str(int(runtime_ok))])
        if result.returncode or not host_matches:
            failures.append(name)
        else:
            print("PASS:", name, flush=True)
    if failures:
        raise SystemExit("FAIL: " + ", ".join(failures))
