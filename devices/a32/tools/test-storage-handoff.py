#!/usr/bin/env python3
"""Execute production CPU selection/service dispatch with host firmware stubs.

The host test proves rejection before storage calls, not PSCI or ARM execution.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]
source = (ROOT / 'xnuloader/loader.c').read_text()
a = source.index('\t/* "bootcpu=N" among the kernel\'s arguments:')
b = source.index('\n\t/* where the kernel will show its signs of life', a)
body = source[a:b]
code = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define CHECKPOINT_SELFTEST 999
#define READ_SYSREG(x) current_cpu
static uint64_t current_cpu;
static struct { int core_shift; } platform, *PLAT = &platform;
static struct { const char *cmdline; } pi;
static int gamut_p3, block_write_requested, block_write_part;
static int hc_requested, block_probe_requested, block_enabled;
static int calls, surveys, starts;
static int starts_with(const char *s, const char *p) { return strncmp(s,p,strlen(p)) == 0; }
void print(const char *s, ...) { (void)s; }
static void charger_start(void) { calls++; }
static void hc_init(void) { calls++; }
static void ufs_survey(void) { calls++; surveys++; }
static void block_start(void) { calls++; starts++; }
static int dispatch(uint64_t checkpoint) {
''' + body + r'''
(void)more_cores; (void)torch_requested; (void)camera_requested;
(void)kernel_mpidr;
return 1;
}
int main(int argc, char **argv) {
 assert(argc == 2);
 int mode = atoi(argv[1]);
 switch (mode) {
 case 0: pi.cmdline="ufs=2"; assert(dispatch(0)==0 && calls==0); break;
 case 1: current_cpu=3; pi.cmdline="battery=1 ufs=2 bootcpu=3 ufs_native=1";
         assert(dispatch(0)==0 && calls==0); break;
 case 2: pi.cmdline="ufs=2 bootcpu=1"; assert(dispatch(0)==1 && starts==1 && surveys==1); break;
 case 3: pi.cmdline=""; assert(dispatch(0)==1 && calls==0); break;
 case 4: pi.cmdline="ufs=1"; assert(dispatch(0)==1 && surveys==1 && starts==0); break;
 case 5: pi.cmdline="ufs=2 bootcpu=1"; assert(dispatch(999)==0 && calls==0); break;
 case 6: pi.cmdline="bootcpu=1"; assert(dispatch(999)==1 && calls==0); break;
 case 7: current_cpu=0x100; platform.core_shift=8; pi.cmdline="ufs=2 bootcpu=1";
         assert(dispatch(0)==0 && calls==0); break;
 default: abort();
 }
 printf("PASS: CPU/storage dispatch scenario %d\n", mode);
}
'''
with tempfile.TemporaryDirectory(prefix='a32-handoff-') as tmp:
    c = Path(tmp)/'test.c'; binary = Path(tmp)/'test'; c.write_text(code)
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=undefined',
                    '-fno-sanitize-recover=all',str(c),'-o',str(binary)],check=True)
    results = [subprocess.run([str(binary),str(i)]).returncode for i in range(8)]
    if any(results): raise SystemExit(f'handoff exits: {results}')
