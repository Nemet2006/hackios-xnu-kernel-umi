#!/usr/bin/env python3
"""Test the staged production framebuffer lookup functions with a fake memory map."""
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[3]
base = root / "out/a32/reference-uefi-merlinx/Silicon/Silicium/SiliciumPkg"


def function(path, name, declaration="EFI_STATUS"):
    text = path.read_text()
    start = text.index(declaration + "\n" + name + " (")
    body = text.index("{", start)
    depth = 1
    end = body + 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


code = r'''
#include <stdint.h>
#include <string.h>
#include <assert.h>
#include <stdio.h>
#define OUT
#define EFI_ERROR(x) ((x)!=0)
#define EFI_SUCCESS 0
#define EFI_NOT_FOUND 1
#define EFI_UNSUPPORTED 2
#define MAX_UINT64 UINT64_MAX
#define MAX_UINT32 UINT32_MAX
#define IN
#define STATIC static
#define VOID void
#define TRUE 1
#define FALSE 0
#define FB_HANDOFF_OFFSET 64
#define DEBUG(x) ((void)0)
#define PcdFrameBufferWidth 1080
#define PcdFrameBufferHeight 2400
#define PcdFrameBufferColorDepth 32
#define PcdFrameBufferXOffset 0
#define FixedPcdGet32(x) (x)
typedef uint64_t EFI_STATUS,EFI_PHYSICAL_ADDRESS,UINT64;
typedef uint32_t UINT32;
typedef uint8_t UINT8;
typedef int BOOLEAN;
static struct {uint64_t Base;uint32_t Width,Height,PitchBytes;} mFbGeometry;
#define FB_WIDTH mFbGeometry.Width
#define FB_HEIGHT mFbGeometry.Height
#define FB_PITCH mFbGeometry.PitchBytes
#define FB_BPP 4
#define FONT_WIDTH 5
#define FONT_HEIGHT 16
static UINT8 scale=2;
static UINT8 GetFontScale(void) {return scale;}
typedef struct {uint64_t Address,Length;} EFI_MEMORY_REGION_DESCRIPTOR;
static EFI_MEMORY_REGION_DESCRIPTOR supplied;
static int mode,calls;
static int clears;
static void ZeroMem(void *p,uint64_t n) {
 assert((uintptr_t)p==supplied.Address && n==supplied.Length);
 clears++;
}
static EFI_STATUS LocateMemoryRegionByName(const char*n,EFI_MEMORY_REGION_DESCRIPTOR*out) {
 calls++;
 if(mode==2 || (mode==1 && strcmp(n,"Display Reserved")==0)) return EFI_NOT_FOUND;
 *out=supplied;return EFI_SUCCESS;
}
'''
code += function(base / "Library/FrameBufferSerialPortLib/FrameBufferSerialPortLib.c", "GetFrameBufferMemory")
code += function(base / "Drivers/SimpleFbDxe/SimpleFb.c", "GetFrameBufferInfos")
code += function(base / "Library/FrameBufferSerialPortLib/FrameBufferSerialPortLib.c", "GeometryFitsRegion", "STATIC\nBOOLEAN")
code += function(base / "Sec/Sec.c", "ClearFrameBuffer", "STATIC\nVOID")
code += r'''
int main(void) {
 for(int test=0;test<7;test++) {
  supplied=(EFI_MEMORY_REGION_DESCRIPTOR){0x80000000,0x1000000};mode=0;
  if(test==1) mode=1;
  if(test==2) mode=2;
  if(test==3) supplied.Address=0;
  if(test==4) supplied.Length=0;
  if(test==5) supplied.Address=UINT64_MAX-10;
  if(test==6) supplied.Length=63;
  uint64_t b=0,l=0;uint32_t w=0,h=0,d=0;calls=0;
  EFI_STATUS s=GetFrameBufferMemory(&b,&l);
  assert((s==0)==(test<2));assert(calls==((mode==1||mode==2)?2:1));
  calls=clears=0;ClearFrameBuffer();
  assert(clears==((test<2||test==6)?1:0));
  assert(calls==((mode==1||mode==2)?2:1));
  if(s==0) assert(b==supplied.Address && l==supplied.Length);
  calls=0;s=GetFrameBufferInfos(&b,&w,&h,&d);
  assert((s==0)==(test<2));assert(calls==((mode==1||mode==2)?2:1));
 }
 for(int test=0;test<9;test++) {
  uint64_t base=0x80000000,length=1080ULL*2400*4+64;
  mFbGeometry.Base=base;mFbGeometry.Width=1080;mFbGeometry.Height=2400;mFbGeometry.PitchBytes=4320;scale=2;
  if(test==1) length--;
  if(test==2) mFbGeometry.Base--;
  if(test==3) mFbGeometry.Base+=length;
  if(test==4) mFbGeometry.PitchBytes=4319;
  if(test==5) mFbGeometry.Height=0;
  if(test==6) scale=0;
  if(test==7) mFbGeometry.Width=1;
  if(test==8) {mFbGeometry.PitchBytes=UINT32_MAX;mFbGeometry.Height=UINT32_MAX;}
  assert(GeometryFitsRegion(base,length)==(test==0));
 }
 puts("PASS: 7 memory-map scenarios through both production lookup functions");
 puts("PASS: 9 production geometry-bound scenarios");
 puts("PASS: 7 SEC clear scenarios with write accounting");
}
'''
with tempfile.TemporaryDirectory(prefix="a32-fb-test-") as temp:
    c = Path(temp) / "test.c"
    binary = Path(temp) / "test"
    c.write_text(code)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", str(c), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
