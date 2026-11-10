#!/usr/bin/env python3
"""Exercise the production resident-load decision and diagnostic result dwell."""
from pathlib import Path
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[3]
s = (ROOT/'xnuloader/loader.c').read_text()
a=s.index('\t{\n\t\tint served_by_file = 0;')
b=s.index('\n\tuint64_t phys_base = win_base;',a)
resident=s[a:b]
a=s.index('\t\t/* Keep the result visible on phones')
b=s.index('\n\t}\n\treboot();',a)
dwell=s[a:b]
code=r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define CHECKPOINT_ENTRY 1
#define CHECKPOINT_SELFTEST 999
static int platform_a32, other_platform;
static int *PLAT = &platform_a32;
static struct { const char *cmdline; uint64_t resident_rd, checkpoint; } pi;
static int loads, stalls, pets;
static int starts_with(const char *s,const char *p) { return strncmp(s,p,strlen(p))==0; }
static void load_resident_from_volume(void) { loads++; }
static void print(const char *s, ...) { (void)s; }
static void wdt_pet(void) { pets++; }
static void stall(uint64_t us) { assert(us==1000000); stalls++; }
static struct { void (*stall)(uint64_t); } services={stall}, *BS=&services;
static void load_decision(uint64_t checkpoint) {
(void)checkpoint;
'''+resident+r'''
}
static void hold_result(void) {
'''+dwell+r'''
}
int main(int argc,char **argv) {
 assert(argc==2); int mode=atoi(argv[1]); pi.cmdline="";
 switch(mode) {
 case 0: load_decision(1); assert(loads==0); break;
 case 1: load_decision(0); assert(loads==1); break;
 case 2: pi.resident_rd=4096; load_decision(0); assert(loads==0); break;
 case 3: pi.cmdline="root_apfs=ufs_apfsfile"; load_decision(0); assert(loads==0); break;
 case 4: pi.checkpoint=1; hold_result(); assert(stalls==120 && pets==120); break;
 case 5: pi.checkpoint=999; hold_result(); assert(stalls==120 && pets==120); break;
 case 6: pi.checkpoint=0; hold_result(); assert(stalls==0); break;
 case 7: PLAT=&other_platform; pi.checkpoint=1; hold_result(); assert(stalls==0); break;
 default: abort();
 }
 printf("PASS: entry probe scenario %d\n",mode);
}
'''
with tempfile.TemporaryDirectory(prefix='a32-entry-') as tmp:
    c=Path(tmp)/'test.c'; binary=Path(tmp)/'test';c.write_text(code)
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=undefined',
                    '-fno-sanitize-recover=all',str(c),'-o',str(binary)],check=True)
    results=[subprocess.run([str(binary),str(i)]).returncode for i in range(8)]
    if any(results):raise SystemExit(f'entry probe exits: {results}')
