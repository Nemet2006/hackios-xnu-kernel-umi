# A32 framebuffer müqaviləsi — 2026-11-08

## Əhatə və qərar

Bu audit host mənbələri üzərində aparılıb. Telefon bu sessiyadan əvvəl rəsmi Android-ə bərpa edilib: canlı ADB `sys.boot_completed=1`, `ro.boot.flash.locked=1`, `ro.boot.verifiedbootstate=green` qaytarıb; istifadəçi Download Mode-da Prenormal bildirib. Bərpa sübutu [checkpoint](../../CHECKPOINT-A32.md) daxilindədir. Bu audit zamanı yeni cihaz əmri, firmware dəyişikliyi və flash edilməyib.

Nəticə: OVL registrinin adı və bit mövqeyi mənbə ilə uyğun gəlir. Bununla belə aktiv LK görüntüsünün stride/format/layer müqaviləsi müəyyən edilməyib. Sabit stride dəyişmək və ya constant-blending yazısını səbəb kimi təqdim etmək üçün sübut yoxdur. Əvvəlki host bounds testləri real scanout uyğunluğunu yoxlamır.

## Mənbələrin mənşəyi

- Samsung A32 kernel referansı: `out/a32/reference-kernel-a32`, commit `9c91f8093f00869692e2ead2d00d09e20b9f25e8`, origin `https://github.com/realahnet/android_kernel_samsung_a32.git`. Audit zamanı `git status --short` boş idi. Bu, icma reposunda saxlanan kernel mənbəyidir; onun telefondakı DXL2 build-i ilə tam uyğunluğu təsdiqlənməyib.
- UEFI referansı: `out/a32/reference-uefi-merlinx`, commit `49462c9374c96229848c9a11f308e33589d6ced3`, mövcud A32 patch-ləri tətbiq edilmiş iş ağacı. Aşağıdakı UEFI müşahidələri həmin dəyişdirilmiş ağaca aiddir, təkcə baza commit-inə deyil.
- Samsung seçim zənciri: [a32_defconfig](../../out/a32/reference-kernel-a32/arch/arm64/configs/a32_defconfig), sətir 1389 (`mt6768`) və 1556 (`CONFIG_MTK_FB=y`); [video/Makefile](../../out/a32/reference-kernel-a32/drivers/misc/mediatek/video/Makefile), sətir 28 platforma altqovluğunu seçir. Başqa MediaTek modelinin `ddp_ovl.c` faylı bu nəticəyə əsas götürülməyib.

## 1. OVL BIT28: registr uyğun gəlir, aktiv pipeline hələ məlum deyil

A32 bootstrap xəritəsi `Display OVL` üçün `0x1400b000`, uzunluq `0x1000` verir: [MemoryMapLib.c](uefi/files/Platforms/Samsung/a32Pkg/Library/MemoryMapLib/MemoryMapLib.c), sətir 47. Samsung [mt6768.dts](../../out/a32/reference-kernel-a32/arch/arm64/boot/dts/mediatek/mt6768.dts), sətir 2821–2823 eyni baza və ölçünü `disp_ovl0` kimi göstərir.

UEFI [PlatformSec.c](../../out/a32/reference-uefi-merlinx/Silicon/MediaTek/MT6768Pkg/Library/PlatformSecLib/PlatformSec.c), sətir 22–35, lookup uğurludursa layer 0 pitch registrinə read/modify/write edir. [PlatformRegisters.h](../../out/a32/reference-uefi-merlinx/Silicon/MediaTek/MT6768Pkg/Library/PlatformSecLib/PlatformRegisters.h), sətir 7–12 offset-i `0x44 + 0x20 * layer`, biti `BIT28` olaraq verir.

Samsung [ddp_reg_ovl.h](https://github.com/realahnet/android_kernel_samsung_a32/blob/9c91f8093f00869692e2ead2d00d09e20b9f25e8/drivers/misc/mediatek/video/mt6768/dispsys/ddp_reg_ovl.h#L136-L144) `L0_PITCH=0x044`, `CONST_BLD=bit 28`, pitch sahəsi isə bit 15:0 müəyyən edir. Deməli həmin OR əməliyyatı bu registr tərifində aşağı pitch bitlərini dəyişmir.

Lakin Samsung [ddp_ovl.c](../../out/a32/reference-kernel-a32/drivers/misc/mediatek/video/mt6768/dispsys/ddp_ovl.c), sətir 739–753, alpha seçimləri və pitch-i birlikdə qurur, constant blending-i yalnız `cfg->const_bld` olduqda aktiv edir. UEFI həmin şərti oxumur. Registr tərifinin uyğunluğu layer-in aktivliyi, saat/MMIO əlçatanlığı, alpha davranışı və LK-nin hansı pipeline-ı işlətməsi barədə sübut deyil. Kernel [primary_display.c](../../out/a32/reference-kernel-a32/drivers/misc/mediatek/video/mt6768/videox/primary_display.c), sətir 9314–9317, `FB_LAYER=0` qaytarır; bu kernel seçimi LK üçün runtime təsdiq sayılmır.

## 2. Stride: 1080 görünən piksel 1080 yaddaş pikseli demək deyil

[a32.dsc](uefi/files/Platforms/Samsung/a32Pkg/a32.dsc), sətir 61–62, 1080×2400 seçir. Staged [SimpleFb.c](../../out/a32/reference-uefi-merlinx/Silicon/Silicium/SiliciumPkg/Drivers/SimpleFbDxe/SimpleFb.c), sətir 114–116 və 188–201, build-time geometry, `PixelsPerScanLine=Width`, `FrameBufferSize=Width*Height*bytes`, 32-bit üçün BGR reserved formatından istifadə edir. [FrameBufferSerialPortLib.c](../../out/a32/reference-uefi-merlinx/Silicon/Silicium/SiliciumPkg/Library/FrameBufferSerialPortLib/FrameBufferSerialPortLib.c), sətir 298–310, ilkin olaraq `PitchBytes=Width*FB_BPP` seçir, yalnız xüsusi handoff magic uyğun gələndə geometry-ni dəyişir.

Samsung [disp_drv_platform.h](../../out/a32/reference-kernel-a32/drivers/misc/mediatek/video/mt6768/videox/disp_drv_platform.h), sətir 35–37, alignment-i 32 verir. [mtkfb.c](../../out/a32/reference-kernel-a32/drivers/misc/mediatek/video/mt6768/videox/mtkfb.c), sətir 102–108 və 687, framebuffer stride/line length hesabında həmin alignment-dən istifadə edir. [primary_display.c](../../out/a32/reference-kernel-a32/drivers/misc/mediatek/video/mt6768/videox/primary_display.c), sətir 9208–9246, capture yolunda görünən enlə yaddaş sətrinin enini ayrıca hesablayır.

32-bit və 1080×2400 üçün hesabi müqayisə:

| Fərziyyə | Pitch (bayt) | 2400 sətir üçün ölçü |
|---|---:|---:|
| UEFI sıx yerləşmə: 1080 piksel | 4320 | 10,368,000 |
| Kernel alignment qaydası: 1088 piksel | 4352 | 10,444,800 |

İkinci sətir LK-dən ölçülmüş dəyər deyil. Əgər LK 4352 bayt istifadə edirsə, UEFI hər sətirdə 32 bayt fərqli ünvan hesablayacaq. Böyük reserved region bu səhvi gizlədə bilər: bütün yazılar sahəyə sığsa da şəkil düzgün çıxmaya bilər. Buna görə `GeometryFitsRegion` testinin keçməsi stride uyğunluğunu sübut etmir. Düzəliş üçün aktiv scanout-un base/offset, pitch, format, görünən ölçü və layer məlumatı lazımdır; 1088-i kor-koranə sabitləmək olmaz.

## 3. FDT formatında əhatə fərqi

Sonrakı canlı yoxlama (2026-11-08): `/sys/firmware/devicetree/base/chosen` siyahısında həm `atag,videolfb`, həm də `atag,videolfb-fb_base_h`, `atag,videolfb-fb_base_l`, `atag,videolfb-vramSize` mövcuddur. Bu Android boot-u üçün split property adlarının yoxluğu fərziyyəsi dəstəklənmir. Dəyərlərin oxunması `Permission denied` verdi; adların mövcudluğu onların uzunluğunu/məzmununu və UEFI girişində eyni FDT-nin verildiyini təsdiqləmir. Sübut: `out/a32/readiness-2026-11-08/device-checks.json`.

Samsung [mtkfb.c](../../out/a32/reference-kernel-a32/drivers/misc/mediatek/video/mt6768/videox/mtkfb.c), sətir 2333–2364, `/chosen` yoxdursa `/chosen@0` axtarır. Əvvəl paket `atag,videolfb` formatını (2269–2296), alınmasa ayrıca property-ləri (2200–2266) oxuyur. Ayrı property-lərdə high/low base, vramSize ilə yanaşı panel-found/init/fps/name məlumatları da var.

A32 [MemoryMapLib.c](uefi/files/Platforms/Samsung/a32Pkg/Library/MemoryMapLib/MemoryMapLib.c), sətir 279–314, yalnız `/chosen` və high/low/vramSize üçlüyünü qəbul edir. Bu üçlük yoxdursa framebuffer descriptor-u yaranmır; lakin bütün memory-map parsing-inin məhz buna görə mütləq fail etməsi nəticəsi çıxmır. Belə uğurlu mapsiz-display halında GOP lookup-u uğursuz ola bilər.

Bu, təsdiqlənmiş dəstək fərqidir. Telefonun LK-si yalnız paket formatını ötürür demək üçün sübut yoxdur. Format əlavə edilməzdən əvvəl konkret LK/FDT artefaktı, paket ABI-si, endian/length/alignment qaydaları müəyyən edilməli və real parser girişindən keçən fixture qurulmalıdır. Hazırkı host stubları telefonun verdiyi property formasını sübut etmir.

### 3a. Real stock DTB-lərin ölçülmüş forması (2026-11-08)

`devices/a32/tools/test-memory-map-fdt.py` real firmware DTB-lərini birbaşa libfdt ilə oxuyur. Ölçülən:

- `base-0.dtb` (99,239 B): `/chosen` var, lakin `atag,videolfb*` xassələri **yoxdur**.
- `a32-r04.dtb` (163,126 B): `/chosen` altında yalnız **split** `atag,videolfb-fb_base_h`,
  `atag,videolfb-fb_base_l`, `atag,videolfb-vramSize` (və panel/fps adları) var.
- `hold-dtb-section.bin` (99,239 B): `base-0.dtb` ilə eyni formadadır.
- Heç birində paket `atag,videolfb` və ya `/chosen@0` node-u yoxdur.

Nəticə: real stock artefaktlar yalnız split formanı göstərir; UEFI parser-in hazırkı split-only davranışı
bu artefaktlarla uyğundur. Buna görə paket formatı və ya `/chosen@0` üçün parser dəyişikliyi **hazırda
əsassızdır** — əvvəlcə canlı LK-nin hansı formanı verdiyi ölçülməlidir. Bu, canlı boot-un həmin DTB-ni
istifadə etdiyini sübut etmir.

## 4. Xüsusi geometry handoff-u avtomatik həll deyil

Serial kitabxana `FB_HANDOFF_MAGIC` ilə record oxuyur. Axtarılan `Silicon/Silicium/SiliciumPkg` və `Platforms/Samsung` ağaclarında həmin simvol üçün producer yazısı tapılmadı: header və serial consumer mövcuddur. SimpleFb yuxarıdakı sabit mode-u yayımlayır. Bu məhdud axtarış bütün mümkün xarici binary-lərdə producer olmadığının sübutu deyil.

[FrameBufferHandoff.h](../../out/a32/reference-uefi-merlinx/Silicon/Silicium/SiliciumPkg/Include/Library/FrameBufferHandoff.h), sətir 5–16, record-un SEC tərəfindən təmizləndiyini fərz edir. A32-də clear live FDT-dən əvvəl display descriptor-u tapmaya bilər; bunun əvvəlki sübutu [BOOT-OBSERVABILITY.az.md](BOOT-OBSERVABILITY.az.md) daxilindədir. Magic və bounds yoxlaması data-nın yeni boot-a aid olduğunu və real scanout-u göstərdiyini təsdiqləmir.

## Növbəti keçid üçün tələb olunan sübut

1. Dəqiq stock LK və ya onun live FDT-si: `/chosen` node adı, framebuffer property forması və reservation. Statik DTB bunu əvəz etmir.
2. Həmin LK mərhələsində real scanout geometry/format/layer; Android açıldıqdan sonrakı kernel geometry-si ayrıca müşahidədir.
3. Həmin sübutdan çıxarılmış parser/geometry fixture-si ilə düzgün stride və rədd edilən natamam formatı yoxlayan host feedback loop.
4. Sonra yalnız sübut olunmuş müqaviləni əhatə edən patch, host yoxlamaları və build. Telefon kilidli/Prenormal ikən eksperimental flash hazır test yolu sayılmır.

Bu audit firmware davranışını dəyişmir və əvvəlki logo problemini həll edilmiş elan etmir. Yeni test və build işlədilməyib: bu sessiyanın dəyişiklikləri sənədləşdirmədir; əvvəlki test/build nəticələri checkpoint-də ayrıca saxlanılıb.
