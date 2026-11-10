#!/usr/bin/env python3
"""Run the production memory-map parser against real libfdt and real stock DTBs.

The firmware links MdePkg's bundled libfdt (see devices/a32/uefi/build-local.sh:
PACKAGES_PATH points at the pinned mu_basecore feed).  This test compiles the
same libfdt sources for the host and links them with the unmodified
MemoryMapLib.c, so the DTB traversal is real rather than a hand-written stub.

Fixtures are either the stock A32 DTBs extracted from the phone firmware or
synthetic trees built in-process.  Synthetic trees are validated by
fdt_check_header before use.  Nothing here proves the live LK handoff FDT.
"""
import struct
import subprocess
import tempfile
from pathlib import Path

from a32_memory_test_support import ROOT, PKG, compile_test

FDT_DIR = (ROOT / 'out/a32/reference-unixnu-merlinx/out/feeds/mu_basecore-89034cbb'
           '/MdePkg/Library/BaseFdtLib/libfdt/libfdt')
DTB_TREES = ROOT / 'out/a32/stock/trees'

FDT_SOURCES = ['fdt.c', 'fdt_ro.c', 'fdt_rw.c', 'fdt_wip.c', 'fdt_sw.c',
               'fdt_check.c', 'fdt_addresses.c', 'fdt_strerror.c']

# The production FdtLib wrapper only forwards to these libfdt calls.  HOB
# services are the one firmware boundary kept as a host stub.
REAL_FDT = r'''
#include <libfdt.h>
int header_calls, traversal_calls, debug_calls;
UINT32 fixture_size;
UINT64 fixture_reserve_size;
int fixture_valid = 1, allocation_fail, hob_builds, hob_present;
EFI_GUID gA32MemoryMapHobGuid = {0};
_Alignas(8) UINT8 hob_store[16384];
int FdtCheckHeader(const void *f) { header_calls++; return fdt_check_header(f); }
UINT32 FdtTotalSize(const void *f) { return (UINT32)fdt_totalsize(f); }
INT32 FdtPathOffset(const void *f, const char *p) { traversal_calls++; return fdt_path_offset(f, p); }
INT32 FdtAddressCells(const void *f, INT32 n) { return fdt_address_cells(f, n); }
INT32 FdtSizeCells(const void *f, INT32 n) { return fdt_size_cells(f, n); }
INT32 FdtFirstSubnode(const void *f, INT32 n) { return fdt_first_subnode(f, n); }
INT32 FdtNextSubnode(const void *f, INT32 n) { return fdt_next_subnode(f, n); }
const void *FdtGetProp(const void *f, INT32 n, const char *p, INT32 *len) { return fdt_getprop(f, n, p, len); }
INTN FdtGetNumberOfReserveMapEntries(const void *f) { return fdt_num_mem_rsv(f); }
int FdtGetReserveMapEntry(const void *f, INTN i, UINT64 *b, UINT64 *s) { return fdt_get_mem_rsv(f, i, b, s); }
void *GetFirstGuidHob(const EFI_GUID *g) {
  assert(g == &gA32MemoryMapHobGuid);
  return hob_present ? hob_store : NULL;
}
void *BuildGuidHob(const EFI_GUID *g, UINTN n) {
  assert(g == &gA32MemoryMapHobGuid);
  hob_builds++;
  if (allocation_fail) return NULL;
  assert(!hob_present && n + 24 <= sizeof(hob_store));
  EFI_HOB_GUID_TYPE *h = (void *)hob_store;
  memset(hob_store, 0, sizeof(hob_store));
  h->Header.HobLength = (UINT16)((n + 24 + 7) & ~7ULL);
  h->Name = *g;
  hob_present = 1;
  return h + 1;
}
'''

MAIN = r'''
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

/* The historical A32 boot header tags/DTB address, inside the envelope the
 * parser enforces (0x40000000..0x140000000). */
#define DTB_ADDR 0x4bc80000UL
#ifndef MAP_FIXED_NOREPLACE
#define MAP_FIXED_NOREPLACE 0x100000
#endif

static void *map_dtb(const char *path, size_t *size) {
  int fd = open(path, O_RDONLY);
  struct stat st;
  void *p;
  if (fd < 0) { perror(path); exit(2); }
  if (fstat(fd, &st) != 0 || st.st_size <= 0) { perror("fstat"); exit(2); }
  size_t pages = ((size_t)st.st_size + 0xfff) & ~(size_t)0xfff;
  p = mmap((void *)DTB_ADDR, pages, PROT_READ | PROT_WRITE,
           MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0);
  if (p == MAP_FAILED) {
    p = mmap((void *)DTB_ADDR, pages, PROT_READ | PROT_WRITE,
             MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, -1, 0);
  }
  if (p == MAP_FAILED) { perror("mmap"); exit(2); }
  if (read(fd, p, (size_t)st.st_size) != (ssize_t)st.st_size) { perror("read"); exit(2); }
  close(fd);
  *size = (size_t)st.st_size;
  return p;
}

static UINT64 fdt_bank_bytes(const void *fdt) {
  UINT64 total = 0;
  int root = fdt_path_offset(fdt, "/");
  if (root < 0) return 0;
  for (int n = fdt_first_subnode(fdt, root); n >= 0; n = fdt_next_subnode(fdt, n)) {
    const char *type = fdt_getprop(fdt, n, "device_type", NULL);
    int len;
    const UINT8 *reg;
    if (type == NULL || strcmp(type, "memory") != 0) continue;
    reg = fdt_getprop(fdt, n, "reg", &len);
    if (reg == NULL || len < 16) continue;
    for (int i = 0; i + 16 <= len; i += 16) {
      UINT64 base = 0, size = 0;
      memcpy(&base, reg + i, 8); base = __builtin_bswap64(base);
      memcpy(&size, reg + i + 8, 8); size = __builtin_bswap64(size);
      (void)base;
      total += size;
    }
  }
  return total;
}

static int overlaps(UINT64 a, UINT64 alen, UINT64 b, UINT64 blen) {
  return a < b + blen && b < a + alen;
}

int main(int argc, char **argv) {
  if (argc != 4) { fprintf(stderr, "usage: %s <mode> <dtb> <expected-status>\n", argv[0]); return 2; }
  int mode = atoi(argv[1]);
  unsigned expected = (unsigned)strtoul(argv[3], NULL, 0);
  size_t size;
  void *fdt = map_dtb(argv[2], &size);
  EFI_MEMORY_REGION_DESCRIPTOR *map = NULL;
  UINT8 count = 0;
  UINT64 usable = 0, display_base = 0, display_len = 0;
  int displays = 0, diagnostics = 0;

  EFI_STATUS status = GetMemoryMapFromFdt(fdt, &map, &count);
  for (UINT8 i = 0; i < count; i++) {
    /* Only descriptors the parser derived from the FDT are RAM pieces; the
     * static bootstrap entries use the same memory type for DXE heap. */
    int lk_ram = !strncmp(map[i].Name, "LK RAM ", 7);
    if (lk_ram) usable += map[i].Length;
    if (!strcmp(map[i].Name, "Display Reserved")) {
      displays++; display_base = map[i].Address; display_len = map[i].Length;
    }
    if (lk_ram && overlaps(map[i].Address, map[i].Length, DTB_ADDR, size)) {
      printf("FAIL: RAM descriptor %u overlaps the FDT itself\n", i);
      return 1;
    }
  }
  printf("INFO: fdt=%s bytes=%zu declared_ram=%llu MiB status=%llu count=%u usable=%llu MiB display=%d\n",
         argv[2], size, (unsigned long long)(fdt_bank_bytes(fdt) >> 20),
         (unsigned long long)status, count, (unsigned long long)(usable >> 20), displays);

  if (status != expected) {
    printf("FAIL: status=%llu expected=%u\n", (unsigned long long)status, expected);
    return 1;
  }
  if (mode == 0) {
    /* Rejected before publishing anything. */
    if (map != NULL || count != 0 || hob_builds != 0) {
      printf("FAIL: rejection published state (map=%p count=%u hob=%d)\n", (void *)map, count, hob_builds);
      return 1;
    }
  } else if (mode == 1) {
    const UINT64 fb = 0x4A000000ULL, vram = 0x1800000ULL;
    if (map == NULL || count == 0 || hob_builds != 1) { printf("FAIL: success did not publish\n"); return 1; }
    if (displays != 1 || display_base != fb || display_len != vram) {
      printf("FAIL: display descriptor base=0x%llx len=0x%llx\n",
             (unsigned long long)display_base, (unsigned long long)display_len);
      return 1;
    }
    if (usable < 0x80000000ULL + 0x20000000ULL) { printf("FAIL: usable RAM below 2.5 GiB\n"); return 1; }
    for (UINT8 i = 0; i < count; i++) {
      if (!strncmp(map[i].Name, "LK RAM ", 7) &&
          (overlaps(map[i].Address, map[i].Length, fb, vram) ||
           overlaps(map[i].Address, map[i].Length, 0x40000000ULL, 0x780000ULL))) {
        printf("FAIL: RAM descriptor %u overlaps a reservation\n", i);
        return 1;
      }
    }
  } else if (mode == 2) {
    if (map == NULL || count == 0 || hob_builds != 1 || displays != 0) { printf("FAIL: unexpected map shape\n"); return 1; }
    if (usable < 0x80000000ULL + 0x20000000ULL) { printf("FAIL: usable RAM below 2.5 GiB\n"); return 1; }
  } else if (mode == 3) {
    if (map != NULL || count != 0 || hob_builds != 0) { printf("FAIL: malformed tree published state\n"); return 1; }
  } else if (mode == 4) {
    if (map != NULL || count != 0 || hob_builds != 0) { printf("FAIL: missing memory published state\n"); return 1; }
  }
  if (mode == 3) diagnostics = debug_calls;
  (void)diagnostics;
  puts("PASS");
  return 0;
}
'''


def pad4(data):
    return data + b'\0' * (-len(data) % 4)


def cells(*values):
    return b''.join(struct.pack('>I', value) for value in values)


def build_fdt(mem_banks=None, chosen=None, reserved=None, mem_rsv=(),
              address_cells=2, size_cells=2):
    """Build a minimal, libfdt-valid flattened device tree."""
    strings = bytearray()
    offsets = {}

    def string_offset(name):
        if name not in offsets:
            offsets[name] = len(strings)
            strings.extend(name.encode() + b'\0')
        return offsets[name]

    def prop(name, value):
        return struct.pack('>III', 3, len(value), string_offset(name)) + pad4(value)

    def node(name):
        return struct.pack('>I', 1) + pad4(name.encode() + b'\0')

    end = struct.pack('>I', 2)
    body = bytearray()
    body += node('')
    body += prop('#address-cells', cells(address_cells))
    body += prop('#size-cells', cells(size_cells))
    if mem_banks:
        body += node('memory')
        body += prop('device_type', b'memory\0')
        body += prop('reg', b''.join(struct.pack('>QQ', base, size) for base, size in mem_banks))
        body += end
    if chosen is not None:
        body += node('chosen')
        for name, value in chosen.items():
            body += prop(name, value)
        body += end
    if reserved is not None:
        body += node('reserved-memory')
        body += prop('#address-cells', cells(2))
        body += prop('#size-cells', cells(2))
        body += prop('ranges', b'')
        for name, properties in reserved:
            body += node(name)
            for prop_name, value in properties.items():
                body += prop(prop_name, value)
            body += end
        body += end
    body += end
    body += struct.pack('>I', 9)
    body = pad4(bytes(body))

    rsv = b''.join(struct.pack('>QQ', base, size) for base, size in mem_rsv) + b'\0' * 16
    off_rsv = 40
    off_struct = off_rsv + len(rsv)
    off_struct += -off_struct % 8
    off_strings = off_struct + len(body)
    total = off_strings + len(strings)
    image = bytearray(total)
    image[0:40] = struct.pack('>10I', 0xD00DFEED, total, off_struct, off_strings, off_rsv,
                              17, 16, 0, len(strings), len(body))
    image[off_rsv:off_rsv + len(rsv)] = rsv
    image[off_struct:off_struct + len(body)] = body
    image[off_strings:] = strings
    return bytes(image)


def fb_props(base=0x4A000000, size=0x1800000):
    return {
        'atag,videolfb-fb_base_h': struct.pack('>I', base >> 32),
        'atag,videolfb-fb_base_l': struct.pack('>I', base & 0xffffffff),
        'atag,videolfb-vramSize': struct.pack('>I', size),
    }


FOUR_GB = [(0x40000000, 0x100000000)]

SYNTHETIC = {
    # name: (fdt bytes, mode, expected status)
    'ram-4g-framebuffer': (build_fdt(FOUR_GB, chosen=fb_props()), 1, 0),
    'ram-4g-no-framebuffer': (build_fdt(FOUR_GB), 2, 0),
    'ram-998m-static': (build_fdt([(0x40000000, 0x3e605000)]), 0, 3),
    'banks-overlap': (build_fdt([(0x40000000, 0x20000000), (0x50000000, 0x10000000)]), 3, 33),
    'dynamic-reservation-ignored': (
        build_fdt(FOUR_GB, reserved=[('zmc-default', {'size': cells(0x1000000)})]), 2, 0),
    'fixed-reservation-subtracted': (
        build_fdt(FOUR_GB, reserved=[('carveout', {'reg': struct.pack('>QQ', 0x80000000, 0x10000000)})]), 2, 0),
    'mem-rsv-entry-subtracted': (build_fdt(FOUR_GB, mem_rsv=((0x70000000, 0x10000000),)), 2, 0),
    'framebuffer-outside-ram': (
        build_fdt(FOUR_GB, chosen=fb_props(base=0x200000000)), 3, 33),
    'bad-address-cells': (build_fdt(FOUR_GB, address_cells=0), 0, 3),
    'no-memory-node': (build_fdt(None), 4, 14),
    'bootstrap-overlap': (
        build_fdt(FOUR_GB, reserved=[('u32', {'reg': struct.pack('>QQ', 0x40000000, 0x100000)})]), 3, 33),
}

REAL = {
    'stock-base-0': (DTB_TREES / 'base-0.dtb', 0, 3),
    'stock-a32-r04': (DTB_TREES / 'a32-r04.dtb', 0, 3),
    'embedded-hold-dtb': (ROOT / 'out/a32/session-checkpoint-2026-10-31/hold-dtb-section.bin', 0, 3),
}


def compile_libfdt(directory):
    objects = []
    for name in FDT_SOURCES:
        source = FDT_DIR / name
        assert source.exists(), f'Missing production libfdt source: {source}'
        obj = directory / (name + '.o')
        subprocess.run(['cc', '-O2', '-I', str(FDT_DIR), '-c', str(source), '-o', str(obj)], check=True)
        objects.append(obj)
    return objects


def main():
    missing = [str(path) for path in [FDT_DIR, *[DTB_TREES / n for n in ('base-0.dtb', 'a32-r04.dtb')]]
               if not path.exists()]
    if missing:
        raise SystemExit('Missing real-DTB test dependency: ' + ', '.join(missing))
    cases = {}
    for name, (path, mode, expected) in REAL.items():
        assert path.exists(), f'Missing real DTB fixture: {path}'
        cases[name] = (bytes(path.read_bytes()), mode, expected)
    for name, (data, mode, expected) in SYNTHETIC.items():
        cases[name] = (data, mode, expected)

    with tempfile.TemporaryDirectory(prefix='a32-fdt-') as directory:
        directory = Path(directory)
        objects = compile_libfdt(directory)
        binary = compile_test(
            directory, MAIN,
            [(PKG / 'Library/MemoryMapLib/MemoryMapLib.c', ''),
             (PKG / 'Library/MemoryMapLib/A32MemoryMapHob.c', '')],
            stubs=REAL_FDT, extra_sources=objects, include_dirs=[FDT_DIR])
        failures = 0
        for name, (data, mode, expected) in cases.items():
            fixture = directory / (name + '.dtb')
            fixture.write_bytes(data)
            run = subprocess.run([str(binary), str(mode), str(fixture), str(expected)],
                                 text=True, capture_output=True)
            print(run.stdout.strip())
            if run.returncode != 0:
                failures += 1
                print(run.stderr.strip())
                print(f'FAIL: {name}')
        if failures:
            raise SystemExit(f'{failures} real-DTB case(s) failed')
        print(f'PASS: {len(cases)} production memory-map cases on real libfdt')


if __name__ == '__main__':
    main()
