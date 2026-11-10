# A32-də iOS quraşdırması — mərhələli bloklayıcı reyestri

Yenilənmə: 2026-11-08. Bu sənəd A32 (SM-A325F, mt6768/MT6769T) üzərində iOS-a gedən yolun hansı
hissəsinin **sübut edildiyini**, hansının **naməlum**, hansının isə **mövcud olmadığını** ayırır.
Məqsəd işi "bitdi" kimi göstərmək deyil; hər mərhələdə növbəti real maneəni adlandırmaqdır.

Qəbul qaydası: host-da keçən test yalnız həmin host kod yolunu sübut edir. Telefonda işləmə,
Samsung bootloader-inin image qəbul etməsi və ya iOS-un açılması ayrıca sübut tələb edir.

## Qısa nəticə

Bu gün ən uzaq **sübut edilmiş** nöqtə host tərəfdir: production yaddaş-xəritəsi parseri real libfdt və
real stock DTB-lər üzərində işləyir; payload validatoru real fayl fixtures ilə 21 ssenarini keçir; A32
UEFI DEBUG build-i keçir. Telefonda isə **heç bir UEFI/XNU/iOS mərhələsi təsdiqlənməyib**.

İki əsas maneə bir-birindən asılı deyil və ikisi də açıqdır:

1. **Bootloader qəbulu və icra:** cihaz kilidlidir (`flash.locked=1`, `verifiedbootstate=green`, vbmeta
   `locked`; istifadəçi OEM LOCK ON + KG Prenormal bildirib). Eksperimental image-in bootloader tərəfindən
   qəbul edilib-edilmədiyi sübut olunmayıb.
2. **Tam APFS üçün yaddaş yolu:** hazırkı "bütün image-ı bir birləşik RAM pəncərəsinə yüklə" yolu 4 GB
   cihazda riyazi olaraq sığmır. Disk-backed yol (loader fayl-backend + XNU storage körpüsü) hələ
   tamamlanmayıb.

## Mərhələlər

| # | Mərhələ | Status | Sübut / səbəb |
|---|---|---|---|
| 0 | Mənbə və artefakt inventarı | **Qismən sübut** | Stock boot, payload, EFI, DTB, APFS hash-ləri və build mənşəyi `out/a32/` altında saxlanılır. Lakin cihazdakı DXL2 ilə community mənbə commit-lərinin tam eyniliyi təsdiqlənməyib. |
| 1 | Bootloader image qəbulu | **Naməlum / bloklanıb** | Boot image host-da düzgün qurulur (Android v2 başlıq, 32 MiB bölməyə sığır), amma Samsung-un qəbulu yoxlanmayıb. Cihaz kilidli/Prenormal olduğu üçün eksperimental boot icra edilə bilməz. |
| 2 | BootShim → SEC → PEI → DXE | **Host kod sübutu; runtime naməlum** | A32 UEFI DEBUG build exit 0 (`out/a32/real-fdt-2026-11-08/uefi-build.log`). Canlı mərhələ işarələri (serial/panel) oxunmayıb. DEBUG SerialPortLib framebuffer-ə bağlıdır, yəni "səssizlik" mərhələnin keçilmədiyini sübut etmir. |
| 3 | Canlı FDT və yaddaş xəritəsi | **Parser sübut; live handoff naməlum** | `test-memory-map-fdt.py` 14/14 keçir: real `base-0.dtb`, `a32-r04.dtb` və `hold-dtb-section.bin` `/memory` = `0x40000000`/`0x3e605000` (998 MiB) elan edir və parser `EFI_UNSUPPORTED` (3) qaytarır. 4 GiB sintetik ağac 21 region / 4003 MiB usable verir. LK-nin canlı FDT verib-vermədiyi yoxlanmayıb. |
| 4 | Framebuffer və erkən müşahidə | **Host parse sübut; scanout naməlum** | Real stock DTB-lərdə `/chosen` yalnız split `atag,videolfb-*` xassələri daşıyır; paket `atag,videolfb` və `/chosen@0` yoxdur. UEFI parser yalnız split high/low/vramSize oxuyur. Real LK-nin hansı formatı verdiyi və stride/format/layer ölçülməyib. |
| 5 | Loader və payload | **Host sübut; device runtime yoxdur** | `test-loader-volume.py` 21 ssenari keçir (kanonik adlar, padding, daxili NUL, duplicate, 128/129 sərhədi, generic-no-platform). `verify-payload.py` checkpoint 0 payload-u qəbul edir. `efi_main` bütün yolu, ARM icrası və firmware davranışı test edilmir. Tarixi hold image checkpoint 998-də qəsdən sonsuz diaqnostikada qalır. |
| 6 | Minimal XNU (bir nüvə, timer/interrupt) | **Mövcud deyil** | A32 konfiqurasiyası MediaTek interrupt/timer/SMP bring-up-ı söndürür. XNU-nun A32-də bir dəfə də başladığına dair sübut yoxdur. |
| 7 | Storage yolu (APFS üçün) | **Qismən mövcud, istifadə olunmur** | **Düzəliş:** əvvəlki "UEFI-də storage sürücüsü yoxdur" iddiası yanlış idi. Cari build FV-də `PartitionDxe`, `Fat`, `MsdcDxe`, `SdDxe`, `EmmcDxe` var (`Build/a32Pkg/DEBUG_CLANGPDB/FV/FVMAIN.Fv.txt`). Amma (a) bu sürücülərin A32 aparatında bind olması yoxlanmayıb, (b) XNU konfiqurasiyasında `CONFIG_HAKIOS_UFS=y`, `CONFIG_UFS=2` artıq açılıb, kernel linki təsdiqlənib, amma mailbox üçün ayrıca nüvə icrası və cihaz sübutu yoxdur, (c) bütün APFS-i RAM-a yükləmə yolu sığmır. |
| 8 | APFS mount və iOS userland | **Mövcud deyil** | `userland/system.apfs` 2,476,728,320 baytdır (2362 MiB). Hazırkı yol `size + 0x08000000 + 0x30000000` = 3,416,252,416 bayt (3258 MiB) birləşik pəncərə tələb edir. 4 GiB DRAM-də ən böyük nəzəri pəncərə 2.75 GiB-dir (payload `0xF0000000`-da bloklayır). APFS-in XNU-da mount edildiyi sübut yoxdur. |
| 9 | Ekran, compositor, touch | **Mövcud deyil** | `device.conf` display/touch/gpu = missing. Mali GPU portu yoxdur; OVL BIT28 uyğunluğu registr səviyyəsindədir, aktiv pipeline sübut deyil. |
| 10 | Gündəlik istifadə sürücüləri | **Mövcud deyil** | Modem, səs, Wi-Fi, kamera, enerji idarəsi `a32.config`-də söndürülüb. iOS-un telefon kimi işləməsi bu mərhələdən əvvəl mümkün deyil. |

## Düzəldilmiş faktlar (əvvəlki sənədlərə qarşı)

- **Storage sürücüsü var:** `a32.fdf` `MediaTekPkg/Extra.fdf.inc` → `SiliciumPkg/Extra.fdf.inc` zəncirini
  işlədir və cari FV-də `MsdcDxe`, `SdDxe`, `EmmcDxe`, `PartitionDxe`, `Fat` var. Əvvəlki checkpoint-in
  "a32.fdf-də storage sürücüsü yoxdur" cümləsi köhnəlib. Bu, sürücünün **hardware-də işlədiyini** sübut
  etmir; yalnız firmware image-ə daxil olduğunu sübut edir.
- **FV praktiki olaraq doludur:** `FVMAIN` ölçüsü `0x337000` (3,371,008 B), tutulmuş `0x336f90`,
  boş yalnız `0x70` (112 B). Yeni DXE modulu əlavə etmək üçün əvvəlcə FV layout/ölçü dəyişikliyi lazımdır;
  sadəcə `INF` sətri əlavə etmək build-i doldura bilər.
- **4 GiB canlı sübut:** `ro.boot.ddr_size=4096MB`, `MemTotal=3,733,036 kB` (~3.56 GiB). Bu, statik
  998 MiB DTB elanı ilə ziddiyyət təşkil edir və LK-nin canlı FDT-ni düzəltməli olduğunu gücləndirir —
  amma LK-nin bunu etdiyini hələ ölçməmişik.

## 2026-11-10 yeniləməsi

Loader-də fayldan blok oxuma xidməti artıq mövcuddur. Host testi offset, son blokun sıfırla
 tamamlanması, sərhədlər və yazı qadağasını yoxlayır. Qısa GetInfo, blok sayında daşma və Read-in
artıq bayt sayı bildirməsi üçün üç regression testi əlavə edildi və səhvlər düzəldildi.
Yeddi A32 host testi və hər iki loader build keçir. Bu, APFS mount və cihaz boot sübutu deyil.
Əvvəlki bütün-image RAM hesabı həmin RAM yoluna aiddir; fayl backend-i bütün image-i RAM-a köçürmür.

Aşağıdakı 1-ci addımın əsas kodu və 2-ci addımın konfiqurasiyası artıq var. Sonrakı yoxlama kernel linkini təsdiqlədi: symbolset xətaları layihənin build wrapper-ində
ayrıca təsnif olunan kext yoxlamalarıdır. Əsas yeni maneə eyni nüvədə loader mailbox xidmətinin
işləməməsidir; mövcud payload da storage arqumentlərini daşımır.
Bax: [Storage inteqrasiya auditi](STORAGE-INTEGRATION-AUDIT.az.md). Yeni sübutlar: `out/a32/storage-audit-2026-11-10/`.

## Növbəti texniki addımlar (prioritet sırası)

1. **Loader fayl-backend blok xidməti:** `\EFI\hakios\system.apfs` faylını `loader_block` protokolu üzərində
   virtual partition kimi təqdim etmək. Bu, bütün APFS-i RAM-a köçürmədən XNU-ya blok oxuma imkanı verir.
   Host testi fayl offset-ləri, son blok, out-of-range, short read və write-refusal ssenarilərini əhatə etməlidir.
2. **XNU storage körpüsünü açmaq:** `CONFIG_HAKIOS_UFS` yalnız shared-page client üçün yenidən nəzərdən
   keçirilməlidir; `ufs_native`/controller register yolu ayrıca qalmalıdır. Bu, XNU build və host testi tələb edir.
3. **Canlı FDT/storage sübutu:** kilid açılmadan və ya read-only kanalla LK-nin verdiyi `/memory`,
   `/chosen` və blok cihazlarının real formasını ölçmək. Statik DTB bunu əvəz etmir.
4. **Bootloader mərhələsi:** yalnız istifadəçi açıq şəkildə unlock/eksperimental boot riskini qəbul edəndə
   və bərpa yolu sənədləşdirildikdə. Bu sənəd heç bir unlock/flash əməliyyatı icazəsi vermir.
5. **Minimal XNU və sürücülər:** yalnız 1–4 mərhələlərindən sonra; əks halda nəticənin səbəbi təcrid oluna bilməz.

## Əlaqəli sənədlər

- [IOS-ROADMAP.az.md](IOS-ROADMAP.az.md) — ümumi mərhələ planı və storage qərar ağacı.
- [LOADER-AUDIT.az.md](LOADER-AUDIT.az.md) — loader/payload/storage körpüsü müqaviləsi.
- [FRAMEBUFFER-CONTRACT-AUDIT.az.md](FRAMEBUFFER-CONTRACT-AUDIT.az.md) — framebuffer/stride sübutu.
- [BOOT-HANDOFF-AUDIT.az.md](BOOT-HANDOFF-AUDIT.az.md) — SEC/DXE yaddaş handoff-u.
- [BOOT-OBSERVABILITY.az.md](BOOT-OBSERVABILITY.az.md) — erkən mərhələ müşahidəsi.
- [../../CHECKPOINT-A32.md](../../CHECKPOINT-A32.md) — sessiya tarixçəsi və canlı cihaz vəziyyəti.
