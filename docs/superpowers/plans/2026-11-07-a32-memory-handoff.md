# A32 Memory Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking. Do not delegate unless the user explicitly authorizes agents.

**Goal:** A32-də yoxlanmış live yaddaş xəritəsini SEC-dən DXE istehlakçılarına təhlükəsiz ötürmək və nəticəni host testləri/build ilə yoxlamaq.

**Architecture:** Mövcud FDT parser və rezerv yoxlamaları saxlanılır. SEC yalnız tam uğurlu xəritəni pointer-siz, versiyalı GUID HOB kimi yayımlayır; ayrıca DXE MemoryMapLib instance HOB-u yoxlayıb öz lokal massivinə köçürür. DXE-də etibarlı HOB yoxdursa nəticə NULL/0 olur.

**Tech Stack:** C, EDK2/PrePi, GUID HOB, Python host harness, cc, mövcud CLANGPDB AARCH64 DEBUG build.

**Spec:** `devices/a32/BOOT-HANDOFF-AUDIT.az.md`; kontekst: `devices/a32/IOS-ROADMAP.az.md`, `CHECKPOINT-A32.md`.

## Global Constraints

- No-device-action qüvvədədir: ADB, Heimdall, USB reset, reboot, boot, flash, erase və cihaz əmrləri yoxdur.
- Mövcud uncommitted iş qorunur; reset/clean/stash və ümumi `git add .` yoxdur.
- `A32_MAX_RAM_BYTES = 2 * SIZE_1GB + SIZE_512MB` həddi dəyişmir; sübutsuz RAM əlavə edilmir.
- HOB descriptor limiti `MAX_ARM_MEMORY_REGION_DESCRIPTOR_COUNT` (hazırda 128), ad uzunluğu `MAX_MEMORY_REGION_NAME_LENGTH` (32) olaraq qalır.
- DXE getter/constructor və HOB validation yolunda DEBUG çağırılmır: framebuffer debug həmin getter-ə geri qayıda bilər.
- HOB yalnız metadata ötürür. Bu iş APFS tutumunu, native storage, Mali, touch, iOS userland və real LK handoff təsdiqini əhatə etmir.
- Build/test uğuru cihazda boot uğuru deyil. Fiziki ünvan üçün rəqəmsal yoxlama onun həqiqətən oxuna bildiyini sübut etmir.

## Review Focus

1. Səhv FDT ölçüsü: traversal başlanmamalıdır — Task 1 call-counter testləri.
2. Uğurlu parsing-dən sonra uğursuz çağırış: əvvəlki live xəritə yeni uğur kimi görünməməlidir — Task 3 state testləri.
3. Kəsilmiş HOB, padding və count hesablaması: sərhəddən kənar oxu olmamalıdır — Task 2 length testləri.
4. Ayrı SEC/DXE global vəziyyəti və debug rekursiyası: yalnız HOB ilə ötürülmə işləməlidir — Task 4 ayrı translation-unit testləri.
5. HOB allocation uğursuzluğu və təkrar publication: yarımçıq və ya ziddiyyətli xəritə yayımlanmamalıdır — Task 3 allocation/duplicate testləri.

## Mövcud vəziyyət və plan qərarları

2026-11-07 mənbə oxunuşunda `BootstrapRangeAllowed()` və parser girişində FDT header/total-size yoxlamaları artıq mövcuddur. `test-bootstrap-ranges.py` 14 hal təsvir edir; bu planın yazılması zamanı testlər icra edilməyib. Auditdə onların hələ yazılmadığı barədə hissə köhnəlib. Bunlar yenidən implementasiya edilməyəcək; əvvəl mövcud davranış yoxlanacaq.

`GetMemoryMap()` hələ statik `gMemoryDescriptor` qaytarır; HOB handoff yoxdur. `MemoryPeim()` SEC-də, `PrePeiSetHobList()` sonrasında çağırılır. Mövcud DSC SEC üçün PrePiHobLib, DXE üçün uyğun HobLib seçir. Generated `out/` faylları əsas mənbə deyil; dəyişikliklər `devices/a32/uefi/files/` altında saxlanılır.

Aşağıdakı format və yeni fayl adları plan təklifidir; əvvəlki cihaz müşahidəsi və ya istifadəçinin ayrıca təsdiqlədiyi ABI kimi təqdim olunmur. Bu yalnız növbəti yaddaş mərhələsinin planıdır; bütün iOS yol xəritəsini bir implementasiya kimi birləşdirmir.

## Fayl sərhədləri

Bu sənəddə `PKG` qısaltması dəqiq olaraq `devices/a32/uefi/files/Platforms/Samsung/a32Pkg` deməkdir.

| Fayl | Məsuliyyət |
|---|---|
| `PKG/Library/MemoryMapLib/MemoryMapLib.c` və `.inf` | Mövcud parser, SEC lokal vəziyyəti, HOB publication |
| `PKG/Include/Guid/A32MemoryMapHob.h` (yeni) | Format, GUID declaration və validate/copy API |
| `PKG/Library/MemoryMapLib/A32MemoryMapHob.c` (yeni) | Hər iki instance-a link edilən, global-sız validation/copy |
| `PKG/Library/MemoryMapDxeLib/MemoryMapDxeLib.c` və `.inf` (yeni) | DXE HOB lookup, lokal copy, mövcud GetMemoryMap API |
| `PKG/a32.dec`, `PKG/a32.dsc` | GUID, include path, SEC/DXE library seçimləri |
| `devices/a32/tools/test-fdt-entry.py` (yeni) | Production parser girişində traversal sırası |
| `devices/a32/tools/test-memory-map-handoff.py` (yeni) | Production producer/consumer və malformed HOB harness |
| `devices/a32/tools/test-bootstrap-ranges.py`, `test-framebuffer-lookup.py` | Mövcud regression testləri |
| `devices/a32/BOOT-HANDOFF-AUDIT.az.md`, `CHECKPOINT-A32.md` | Yoxlanmış nəticə və qalan runtime boşluqları |

### Task 1: Mövcud FDT və bootstrap qorumasını yoxlamaq

**Files:** Mövcud MemoryMapLib.c; yeni `devices/a32/tools/test-fdt-entry.py`; mövcud bootstrap testi.

**Interfaces:** Mövcud `EFI_STATUS GetMemoryMapFromFdt(CONST VOID *, EFI_MEMORY_REGION_DESCRIPTOR **, UINT8 *)` və `BOOLEAN BootstrapRangeAllowed(UINT64, UINT64, CONST A32_RANGE *, UINTN, CONST A32_RANGE *, UINTN)` dəyişmir.

- [x] `python3 devices/a32/tools/test-bootstrap-ranges.py` icra et. Gözlənən: `PASS: 14 bootstrap range cases...`. Uyğunsuzluğu düzəltməzdən əvvəl səbəbini ayırd et.
- [x] Yeni harness-də production parser-i FdtLib stub-ları ilə çağır; header və traversal çağırışlarını say. Sabit fiziki ünvanları dereference etməyən stub-lardan istifadə et; guard kodunun kopyasını test etmə.
- [x] `reject_before_header`: NULL, unaligned, 0x40000000-dan aşağı, header-in 0x140000000 sərhədini keçməsi üçün `header_calls == 0 && traversal_calls == 0`; nəticə NULL/0. `reject_before_traversal`: invalid header, totalsize header-dən kiçik, 16 MiB-dan böyük, ünvan son sərhədini keçən totalsize üçün `traversal_calls == 0`. Düzgün ölçü üçün traversal-a çatdığını ayrıca təsdiqlə.
- [x] `python3 devices/a32/tools/test-fdt-entry.py` icra et. Mövcud qoruma düzgün olduqda ilk icra PASS ola bilər; bunu yeni düzəliş kimi təqdim etmə. Xəta varsa yalnız onu göstərən testdən sonra minimal düzəliş et və hər iki testi təkrar icra et.
- [x] Bu task-ın diff-ini yoxla; yalnız ona aid hunks üçün ayrıca commit hazırla. Əvvəldən untracked olan bütün A32 qovluğunu təsadüfən stage etmə.

### Task 2: Pointer-siz HOB formatı və ortaq validator

**Files:** Yeni `PKG/Include/Guid/A32MemoryMapHob.h`, `PKG/Library/MemoryMapLib/A32MemoryMapHob.c`, `devices/a32/tools/test-memory-map-handoff.py`; `PKG/a32.dec`.

**Interfaces:** `EFI_STATUS A32CopyMemoryMapHob(CONST VOID *Data, UINTN DataSize, EFI_MEMORY_REGION_DESCRIPTOR *Destination, UINTN Capacity, UINT8 *Count)`. Count girişdə sıfırlanır; validation tam bitmədən Destination dəyişmir.

Format: 16 baytlıq dörd UINT32 sahə — `Version=1`, `DescriptorCount`, `DescriptorSize=sizeof(EFI_MEMORY_REGION_DESCRIPTOR)`, `Reserved=0`; sonra descriptor-ların bayt kopyası. GUID simvolu `gA32MemoryMapHobGuid`; implementer bir unikal UUID yaradıb yalnız DEC-də qeyd edir. Paket `[Includes] Include` ixrac edir. Eyni firmware build-in AARCH64 producer/consumer ABI-si istifadə edilir; format xarici persistent disk ABI-si deyil.

- [x] Harness-də `round_trip`, `reject_lengths`, `reject_metadata`, `reject_descriptor` testlərini yaz. 1 və 128 descriptor round-trip-də bütün sahələr eyni qalmalıdır; count 0/129/UINT32_MAX, wrong version/size, reserved!=0, NULL/truncated data rədd edilməlidir. Rədd zamanı count=0 və destination sentinel dəyişməməlidir.
- [x] Length testində 16-byte header və descriptor uzunluğu əvvəl overflow-safe hesablanır; buffer həmin uzunluqdan kiçikdirsə reject, yalnız HOB-un 8-byte alignment padding-i qədər əlavə bayta icazə verilir. HOB-un UINT16 ümumi uzunluğuna sığma ayrıca yoxlanır.
- [x] Descriptor testində 32 baytda NUL olmayan ad, zero length, address+length overflow və capacity<count rədd edilir. FDT parser-in semantik etibarlılığı saxlanır; HOB validator yeni RAM siyasəti icad etmir.
- [x] `python3 devices/a32/tools/test-memory-map-handoff.py` icra et; ilkin uğursuzluq yeni production API-nin olmamasından gəlməlidir, test harness xətasından yox.
- [x] Ortaq API-ni implementasiya et; unaligned Data girişini lokal header-ə CopyMem ilə oxu. Bütün validation bitdikdən sonra descriptor-ları köçür və count-u təyin et. Global state, HOB lookup və DEBUG bu faylda yoxdur.
- [x] Eyni test əmrini icra et; bütün hallar PASS. Yalnız task fayllarını seçərək diff/commit hazırla.

### Task 3: SEC-də atomik publication və uğurlu lokal xəritə

**Files:** `PKG/Library/MemoryMapLib/MemoryMapLib.c`, `.inf`; ortaq header; handoff harness.

**Interfaces:** Yeni `EFI_STATUS A32PublishMemoryMap(CONST EFI_MEMORY_REGION_DESCRIPTOR *Map, UINT8 Count)`; mövcud GetMemoryMap API dəyişmir. Task 2 formatını istifadə edir.

- [x] Production producer üçün HobLib stubs əlavə et: `publish_once`, `allocation_failure`, `parse_failure_no_publish`, `success_then_failure`, `duplicate_publication`. Allocation NULL olduqda EFI_OUT_OF_RESOURCES; invalid/yarımçıq map üçün yeni HOB sayı 0; ikinci publication üçün EFI_ALREADY_STARTED gözlənilir.
- [x] Testi icra et və mövcud kodun handoff/state tələblərini ödəmədiyini göstər.
- [x] INF-ə A32 package, HobLib, GUID və ortaq validation source əlavə et. Producer əvvəl ortaq validator ilə map-i yoxlasın, sonra `BuildGuidHob` ilə tək allocation edib doldursun. Ayrı heap allocation tələb olunmur. Eyni GUID artıq varsa ikinci HOB yaratmasın.
- [x] Parser girişində lokal live-ready vəziyyətini söndür. Bütün parser yoxlamaları, xüsusilə usable RAM həddi keçdikdən sonra publication çağır; uğursuzluqda outputs NULL/0 saxla və status qaytar. Yalnız publication uğurundan sonra lokal ready/count və outputs qur.
- [x] SEC getter parsing-dən əvvəl bootstrap cədvəli, uğurlu publication-dan sonra lokal live xəritə qaytarsın. Sonrakı uğursuz parser çağırışı əvvəlki lokal live nəticəni aktiv saxlamasın. Boot axını həmin xəta ilə dayanır; əvvəl yayımlanmış HOB-u silmək üçün uydurma rollback əlavə etmə.
- [x] Handoff, FDT entry və bootstrap testlərini icra et; allocation failure-də çağıranın failure aldığına bax. Task diff/commit hazırla.

### Task 4: DXE istehlakçısı və ayrı library link edilməsi

**Files:** Yeni `PKG/Library/MemoryMapDxeLib/MemoryMapDxeLib.c`, `.inf`; `PKG/a32.dsc`; handoff harness.

**Interfaces:** `VOID GetMemoryMap(EFI_MEMORY_REGION_DESCRIPTOR **MemoryDescriptor, UINT8 *MemoryDescriptorCount)`; Task 2 validator. DXE parser ixrac etmir.

- [x] SEC və DXE production source-larını ayrı translation unit kimi compile et, test üçün getter simvollarını ayır. Aralarında yalnız fake HOB store paylaş; global descriptor massivini paylaşma.
- [x] `missing_hob_returns_empty`, `malformed_hob_returns_empty`, `independent_round_trip`, `copy_lifetime`, `no_debug_recursion` testlərini əlavə et. Valid map-də `Display Reserved` sahələri eyni olmalı; producer/source buffer dəyişəndə DXE lokal copy dəyişməməlidir. Invalid HOB-da NULL/0 və sıfır DEBUG çağırışı gözlənilir. HOB hələ yoxdursa getter sonrakı çağırışda yenidən axtara bilməlidir.
- [x] Testi icra et və yeni DXE API/library olmadığından uğursuzluğu təsdiqlə.
- [x] DXE getter ilk uğurlu lookup-da `GetFirstGuidHob`/data-size vasitəsilə validasiya və lokal copy etsin, uğurlu copy-ni image ömrü boyu saxlasın. Xəta zamanı statik RAM fallback və DEBUG olmasın.
- [x] DSC-nin ümumi MemoryMapLib seçimini DXE consumer-ə yönəlt, `[LibraryClasses.common.SEC]` ilə parser/producer instance-ını seç. DXE INF-də ortaq source, A32 package, GUID, BaseMemoryLib/HobLib tələblərini yaz; FdtLib asılılığı əlavə etmə.
- [x] `python3 devices/a32/tools/test-memory-map-handoff.py` və `python3 devices/a32/tools/test-framebuffer-lookup.py` icra et. Handoff harness-də mövcud production display lookup-a DXE getter-i bağlayıb valid HOB üçün `Display Reserved` tapıldığını, missing HOB üçün tapılmadığını yoxla. Task diff/commit hazırla.

### Task 5: Firmware inteqrasiyası və sübutun saxlanması

**Files:** Yalnız zəruri library inteqrasiya düzəlişləri; `devices/a32/BOOT-HANDOFF-AUDIT.az.md`, `CHECKPOINT-A32.md`.

**Interfaces:** Mövcud `devices/a32/uefi/apply.sh` və `devices/a32/uefi/build-local.sh`; yeni CLI/build rejimi yaradılmır.

- [x] Dörd host testi icra et: `test-bootstrap-ranges.py`, `test-fdt-entry.py`, `test-memory-map-handoff.py`, `test-framebuffer-lookup.py` (`python3 devices/a32/tools/<file>`). Hamısı exit 0 və assertion-lar PASS olmalıdır.
- [x] `sh devices/a32/uefi/build-local.sh` icra et. Gözlənən DEBUG AARCH64 build exit 0; asılılıq çatışmırsa konkret çatışmazlığı yaz, nəticəni PASS adlandırma.
- [x] `out/a32/reference-uefi-merlinx/Build/a32Pkg` altında generated AutoGen/library list/map artefaktlarını araşdır: SEC producer-i, SimpleFbDxe və debug istifadə edən DXE image-ləri consumer-i link etməlidir. Hər ikisində eyni GUID olmalıdır; DXE-də FDT parser simvolu olmamalıdır. Dəqiq artefakt yollarını auditə yaz.
- [x] `sh devices/a32/uefi/apply.sh` ikinci dəfə icra et; exit 0 və staged source fərqi olmaması idempotence sübutudur. Firmware/FV ölçüsünü hazır build-dən qeyd et; köhnə boş yer rəqəmini limit kimi təkrarlama.
- [x] Audit və checkpoint-ə hansı test/build-in həqiqətən icra edildiyini, nəticə/log/hash yollarını, dəyişən mənbə vəziyyətini yaz. Köhnə “guard yoxdur” hissəsini düzəlt. Erkən shim/stack ownership, real LK x0/FDT, OVL BIT28 və real panel formatını açıq runtime boşluğu saxla.
- [x] Yalnız bu işin diff-ini whitespace və scope baxımından yoxla. Mövcud `xnu/hakios.patch` whitespace və başqa əvvəlki dəyişiklikləri bu task-a qatma. Seçilmiş task dəyişiklikləri üçün commit hazırla; sonra istifadəçiyə host nəticəsi ilə cihaz müşahidəsi arasındakı sərhədi bildir.

## Planın öz yoxlaması

Auditin üç implementasiya hissəsi Tasks 1–4-də, build/link sübutu Task 5-də qarşılanır. BootShim scratch və real LK handoff ayrıca cihaz/mənbə sübutu tələb etdiyindən bu plan onları həll olunmuş saymır. Format/validator API-si producer və consumer üçün eynidir. Beş review riski konkret testlərə bağlanıb. Planın yazılması implementasiya, test icrası və ya cihaz icazəsi deyil.

## İcra nəticəsi — 2026-11-07

5 tapşırıq icra edildi; test/build nəticələri `devices/a32/BOOT-HANDOFF-AUDIT.az.md` və `out/a32/memory-handoff-2026-11-07/` içindədir. Mövcud untracked A32 mənbələrini əvvəlki işlə birlikdə commit etməmək üçün task commit-ləri əvəzinə başlanğıc snapshot-a nəzərən diff hazırlandı. Ayrı branch istifadə edildi, ayrıca worktree yaradılmadı; tələb olunan mənbə və build feed-ləri mövcud iş qovluğunda idi. İstifadəçinin delegation qadağasına görə son baxış müəllif tərəfindən edildi. Telefon əməliyyatı yoxdur.
