#!/usr/bin/env python3
"""Exercise production bootstrap interval validation with host boundary cases."""
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[3]
text = (root / "devices/a32/uefi/files/Platforms/Samsung/a32Pkg/Library/MemoryMapLib/MemoryMapLib.c").read_text()
start = text.index("STATIC\nBOOLEAN\nBootstrapRangeAllowed")
end = text.index("STATIC\nUINT64\nReadCells", start)
code = r'''
#include <stdint.h>
#include <stddef.h>
#include <assert.h>
#include <stdio.h>
#define STATIC static
#define CONST const
#define TRUE 1
#define FALSE 0
#define MAX_UINT64 UINT64_MAX
typedef uint64_t UINT64;
typedef size_t UINTN;
typedef int BOOLEAN;
typedef struct {UINT64 Base,End;} A32_RANGE;
'''
code += text[start:end]
code += r'''
int main(void) {
 A32_RANGE banks[]={{0x40000000,0x140000000}};
 A32_RANGE cuts[]={{0x48000000,0x49000000}};
 assert(BootstrapRangeAllowed(0x40000000,0x40000,banks,1,cuts,1));
 assert(BootstrapRangeAllowed(0x40080000,0x300000,banks,1,cuts,1));
 assert(BootstrapRangeAllowed(0x40380000,0x3c00000,banks,1,cuts,1));
 assert(BootstrapRangeAllowed(0x40000000,0x8000000,banks,1,cuts,1));
 assert(!BootstrapRangeAllowed(0x40000000,0x8000001,banks,1,cuts,1));
 assert(BootstrapRangeAllowed(0x49000000,0x1000,banks,1,cuts,1));
 assert(!BootstrapRangeAllowed(0x48ffffff,0x1000,banks,1,cuts,1));
 assert(!BootstrapRangeAllowed(0x3fffffff,0x1000,banks,1,cuts,1));
 assert(!BootstrapRangeAllowed(0x13fffffff,2,banks,1,cuts,1));
 assert(!BootstrapRangeAllowed(UINT64_MAX-15,16,banks,1,cuts,1));
 assert(!BootstrapRangeAllowed(0x40000000,0,banks,1,cuts,1));
 assert(!BootstrapRangeAllowed(0x40000000,1,banks,0,cuts,1));
 A32_RANGE split[]={{0x40000000,0x41000000},{0x41000000,0x42000000}};
 assert(!BootstrapRangeAllowed(0x40fff000,0x2000,split,2,NULL,0));
 assert(BootstrapRangeAllowed(0x41000000,0x1000000,split,2,NULL,0));
 puts("PASS: 14 bootstrap range cases including exact boundaries, overlap and overflow");
}
'''
with tempfile.TemporaryDirectory(prefix="a32-ranges-") as directory:
    c = Path(directory) / "test.c"
    binary = Path(directory) / "test"
    c.write_text(code)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", str(c), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
