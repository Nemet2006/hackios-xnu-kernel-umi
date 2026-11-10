# A32 boot handoff auditi

Yenilənmə: 2026-11-07. Mənbə və host yoxlamaları; LK-nin real giriş registrləri hələ ölçülməyib.

## Live xəritənin istifadəçilərə çatdırılması

Əvvəl `MemoryInitPei` live FDT nəticəsini MMU/resource HOB-ları üçün istifadə etsə də `GetMemoryMap` yalnız statik cədvəli qaytarırdı. Həmin cədvəldə `Display Reserved` olmadığından uğurlu parsing belə GOP lookup-unu təmin etmirdi. 2026-11-07 implementasiyası bu modul sərhədini ayrıca SEC producer və DXE consumer ilə keçir; host nəticəsi aşağıdadır.

Təkcə getter-i `gFdtMemoryDescriptor`-a yönəltmək tam həll deyil: BASE kitabxanası SEC və hər DXE image-ə ayrıca link edilir, `static` vəziyyət paylaşılmır. Bu sadə dəyişiklik araşdırılıb saxlanmadı. Səhv pointer-in SEC image daxilində yaşadığını DXE-yə ötürmək də olmaz.

İmplementasiya edilmiş müqavilə:

1. A32-yə məxsus GUID HOB formatı: version, descriptor count, descriptor byte size və descriptor-ların kopyası. Pointer daşınmır. Count yuxarı limiti mövcud map limiti ilə eyni olur; length hesabında overflow rədd edilir.
2. SEC parser, rezervlərin çıxılması və xəritə yoxlaması uğurlu olduqdan sonra bu HOB-u bir dəfə yaradır. HOB qurulması uğursuz olsa handoff davam etmir. Yarımçıq xəritə heç vaxt yayımlanmır.
3. SEC üçün getter lokal uğurlu xəritəni qaytara bilər; parsing-dən əvvəl yalnız bootstrap cədvəli mövcuddur. DXE variantı fərqli library instance ilə HOB-dan yoxlanmış kopyanı oxuyur. DXE-də HOB yoxdursa statik RAM-ı tam live xəritə kimi göstərmək olmaz; getter boş nəticə qaytarmalı və display lookup uğursuz olmalıdır.
4. DXE library constructor/getter invalid HOB haqqında DEBUG çağırmamalıdır: debug özü MemoryMapLib-ə qayıdaraq rekursiya yarada bilər. HOB pointer ömrü və lokal kopyanın ömrü driver image-i qədərdir.
5. Host testləri SEC və DXE production kodunu ayrı translation unit kimi link edir; yalnız fake HOB store paylaşılır. Missing/truncated/wrong-version/wrong-size/too-many-descriptors və 1/128 descriptor round-trip yoxlanıb. A32 DEBUG build və producer/consumer link seçimi də yoxlanıb.

Adi resource/memory-allocation HOB-ları artıq qurulur, lakin region adlarını bu library API üçün eyni formada daşımır. Ona görə həmin HOB-ların mövcudluğu `Display Reserved` axtarışının işləməsini sübut etmir. GUID handoff dizaynı yalnız metadata paylaşır; əlavə RAM yaratmır.

## Sabit bootstrap regionlarının live rezervlərlə ziddiyyəti

Mövcud cədvəl stack `[0x40000000,0x40040000)`, FD `[0x40080000,0x40380000)` və heap `[0x40380000,0x43f80000)` sahələrini SYS_MEM kimi təqdim edir. Parser artıq `BootstrapRangeAllowed()` vasitəsilə bu sahələrin bir təsdiqlənmiş RAM bankına tam daxil olduğunu və LK reserved-memory/FDT/initrd/framebuffer ilə kəsişmədiyini çıxışa kopyalamazdan əvvəl yoxlayır. Bu qoruma 2026-11-07 sessiyasının əvvəlində artıq mənbədə var idi; bu sessiyada yenidən yazılmayıb.

14 host halı exact-boundary, bir bayt overlap, bankdan kənar interval, split-bank və overflow davranışını təsdiqləyir. RAM minimumu dəyişməyib. Bu yoxlama erkən shim/stack istifadəsini geriyə dönük qorumur; onların təhlükəsizliyi LK boot müqaviləsindən ayrıca təsdiqlənməlidir.

## BootShim və FDT girişinin sərhədləri

BootShim mənbəyi x0-ı dəyişmir. FD köçürməsi üçün scratch `0x403f0000` olur (FD base + 3 MiB + 0x70000), gələcək DXE heap-in içindədir. Ardıcıllıqla təkrar istifadə özü xəta deyil; shim bitməzdən əvvəl həmin sahənin bootloader üçün başqa aktiv məna daşımaması yoxlanmalıdır. Dəqiq copy-loop uzunluğu və source/destination intervalı hazır image-dən yoxlanmalıdır.

PEI patch x0 üçün tarixi `[0x40000000,0x140000000)` sərhədini yoxlayır. Parser artıq header-in bu intervala sığmasını, 8-byte alignment-i, totalsize üçün header minimumunu və 16 MiB maksimumunu traversal-dan əvvəl yoxlayır. 11 production-function host halında invalid giriş traversal-a çatmır; düzgün sərhədli giriş çatır. Bu qoruma da sessiyadan əvvəl mövcud idi. Fiziki ünvanın oxuna bildiyini firmware müqaviləsi olmadan yalnız rəqəmsal bounds yoxlaması sübut etmir.

## Ardıcıllıq

Fixed-region/FDT giriş yoxlamaları və HOB handoff host mərhələsi tamamlanıb. Production `LocateMemoryRegionByName` DXE getter ilə `Display Reserved` regionunu tapır; HOB yoxdursa tapmır. Sonrakı araşdırma real framebuffer formatı, stride, inherited OVL BIT28 əməliyyatı və görünən mərhələ işarəsidir. Hazırkı no-device-action məhdudiyyəti dəyişmir.

## 2026-11-07 yoxlama sübutu

Plan: `docs/superpowers/plans/2026-11-07-a32-memory-handoff.md`. Mənbə kökü: `devices/a32/uefi/files/Platforms/Samsung/a32Pkg/`.

- Format: `Include/Guid/A32MemoryMapHob.h`, versiya 1, 16-byte header, maksimum 128 descriptor, pointer yoxdur. `A32CopyMemoryMapHob` bütün girişi yoxlamadan destination-a yazmır; qısa data, səhv metadata, NUL-suz ad, sıfır ölçü və interval overflow-u rədd edilir.
- `Library/MemoryMapLib/MemoryMapLib.c` yalnız parser uğurundan sonra HOB yaradır. Allocation failure və duplicate publication xəta qaytarır. SEC getter uğurlu xəritəni lokal saxlayır; növbəti uğursuz parser çağırışı onu aktiv saxlamır.
- `Library/MemoryMapDxeLib/MemoryMapDxeLib.c` ayrıca instance-dır. HOB-dan validasiya edilmiş lokal copy saxlayır; invalid/missing HOB üçün NULL/0 qaytarır. Getter/validator DEBUG çağırmır. Consumer source buffer və SEC globals dəyişdikdən sonra da öz copy-sini saxlayır.
- Bütün 5 `devices/a32/tools/test-*.py` skripti exit 0: bootstrap 14, FDT giriş 11, framebuffer 7 lookup + 9 geometry + 7 SEC clear, əvvəlki loader 8 hal, yeni HOB validator qrupu + 5 SEC + 4 DXE ssenarisi. Yeni C harness `-Wall -Wextra -Werror -fsanitize=undefined` ilə işləyir.
- `sh devices/a32/uefi/build-local.sh`: DEBUG AARCH64 CLANGPDB, exit 0, 18 saniyə. 57 image-in library siyahısı eyni GUID və düzgün producer/consumer seçimini göstərir. DXE map-larında parser simvolu yoxdur; LTO olduğundan əsas link sübutu library siyahısıdır.
- Staging ikinci dəfə işlədilib; 113 staged faylın hash-i dəyişməyib.

Build kökü `out/a32/reference-uefi-merlinx/Build/a32Pkg/DEBUG_CLANGPDB/` altında konkret link sübutları:

| Modul | Library siyahısı (build kökünə nəzərən) |
|---|---|
| SEC | `AARCH64/SiliciumPkg/Sec/Sec/OUTPUT/static_library_files.lst` |
| SimpleFbDxe | `AARCH64/SiliciumPkg/Drivers/SimpleFbDxe/SimpleFbDxe/OUTPUT/static_library_files.lst` |
| DXE Core | `AARCH64/MdeModulePkg/Core/Dxe/DxeMain/OUTPUT/static_library_files.lst` |

Hər modulun qonşu `DEBUG/AutoGen.c` faylında GUID dəyəri eynidir; `DEBUG/*.map` GUID simvolunu ehtiva edir. SEC PrePiHobLib, DXE Core DxeCoreHobLib, SimpleFbDxe DxeHobLib istifadə edir.

`FV/SILICIUM_UEFI.fd`: 3,145,728 bayt; SHA-256 `abf66387405cd737b6cad21e307b192cb7b0fe3e0ae0df7dbdea99ffff455af7`. FVMAIN 0x337000, istifadə 0x336f90, boş 0x70; compressed FD-də boş sahə 0x25c3d0. FVMAIN-in cari boşluğu gələcək build üçün sabit maksimum deyil.

Loglar, link inventarı, hash-lər, başlanğıc snapshot və diff: `out/a32/memory-handoff-2026-11-07/`. Kod dəyişiklikləri ayrıca `codex/a32-memory-handoff-20261107` branch-ində commit edilmədən saxlanılıb; əvvəlki untracked A32 işi commit-ə qatılmayıb. Son baxış müəllifin öz baxışıdır; subagent istifadə edilməyib.

## Sübutun sərhədləri

Host harness FdtLib/HobLib sərhədlərini stub edir; real Samsung FDT-si və fiziki RAM oxunuşunu sübut etmir. Malformed xüsusi HOB payload-u yoxlanır; ümumi firmware HOB list-in etibarlı olduğu HobLib-in mövcud müqaviləsidir. Bütövlükdə korlanmış HOB zəncirini təhlükəsiz gəzmək bu decoder-in təminatı deyil.

Pinned PrePiHobLib allocation failure-də NULL qaytarmazdan əvvəl ASSERT edə bilər: DEBUG build həmin nöqtədə dayana bilər. Host test producer-in NULL failure yolunu təsdiqləyir; runtime-da mütləq statusla geri qayıdış vəd etmir. Hər iki halda handoff davam etdirilmir.

Erkən shim/stack və relocation scratch ownership, LK x0/FDT, panel formatı/stride, OVL BIT28 və cihazda UEFI/XNU başlanğıcı hələ təsdiqlənməyib. Yeni firmware boot image-ə paketlənməyib və flash edilməyib.
