# A32-də iOS üçün sübuta əsaslanan iş planı

Yenilənmə: 2026-11-05. Hədəf SM-A325F / A32 4G-dir. Bu sənəd əvvəlki söhbət planını əvəz edir. Hazırlıq planıdır; cihazda UEFI/XNU/iOS işləməsi təsdiqlənməyib.

## Məqsəd və iş qaydası

Son məqsəd A32-də iOS userland-ının açılması, görüntü və toxunma ilə idarə olunması, bundan sonra təkrar boot və məlumatların saxlanmasıdır. Kiçik test proqramı və launchd başlanğıcı aralıq nəticələrdir. Apple xidmətləri və App Store bu repo tərəfindən təmin edilmir; onların işləməsi bu portun qəbul meyarı deyil. Telefon kimi gündəlik istifadə üçün modem, səs, enerji və digər sürücülər ayrıca tamamlanmalıdır.

Hər dəyişiklikdən əvvəl qeyd: problem → sübut → dəyişiklik → növbəti mərhələyə təsir → yoxlama → uğursuzluqda çıxış yolu. Hər cəhdin mənbə reviziyası, lokal diff-i, konfiqurasiyası, artefakt hash-i və logu bir-birinə bağlanmalıdır. Bir sınaqda bir əsas fərziyyə yoxlanmalıdır. Məlumat çatışmazlığı uğur kimi qəbul edilmir.

Cihaz əməliyyatlarına əvvəlki qadağa qüvvədədir. Aşağıdakı cihaz mərhələləri gələcək işdir; boot/flash, ADB, USB reset və bərpa əməliyyatı bu planla avtomatik icazə almır. Mövcud uncommitted iş qorunur.

## Düzəldilən boşluqlar və sübutlar

- `xnuloader/loader.c` içində checkpoint 998 qəsdən sonsuz diaqnostika gözləməsidir. Onu söndürmək Samsung loqosunda qalmanın səbəbini həll etmiş sayılmır.
- `choose_window()` və `load_resident_from_volume()` hazırkı APFS üçün kifayət qədər birləşik RAM tapa bilmir: checkpoint hesabında tələb 3,416,252,416 bayt, ideal ən böyük pəncərə 2,952,790,016 baytdır. Bu hesab tarixi RAM sərhədinə əsaslanır; canlı xəritəni əvəz etmir.
- UEFI BlockIO XNU block cihazı demək deyil. Mövcud `block_poll()` loader-in gözləmə dövründə işləyir; XNU tərəfdə `drivers/storage/hakios.ufs.c` ortaq səhifədən istifadə edir. A32 konfiqurasiyası həmin sürücünü söndürür. `ufs=2` yolu `hc_init()` də çağırır. Onu olduğu kimi A32-də açmaq olmaz.
- `docs/concepts/architecture.md`-dəki fastboot yolu Samsung üçün təsdiqlənməyib. Samsung boot image ölçüsü və başlıq uyğunluğu bootloader-in image-i qəbul etdiyini sübut etmir.
- Live FDT parser-in çağırışı mövcuddur. Problem onun yoxluğu deyil; LK-dən düzgün FDT gəlib-gəlmədiyi məlum deyil. Statik DTB-dən bütün RAM-ı təhlükəsiz elan etmək olmaz.
- GOP/framebuffer yalnız görüntü çıxışıdır. iOS compositor və qrafika uyğunluğu ayrıca işdir; Adreno implementasiyası Mali-yə daşınmış sayılmır.

## Mərhələlər və keçid şərtləri

2026-11-05 boot auditi əlavə bloklayıcı müəyyən etdi: live xəritə SEC/DXE arasında paylaşılmır və sabit bootstrap sahələrinin live rezervlərlə ziddiyyəti yoxlanmır. [BOOT-HANDOFF-AUDIT.az.md](BOOT-HANDOFF-AUDIT.az.md) bu mərhələlərin konkret implementasiya və test müqaviləsidir; GOP işi bundan asılıdır. Sadəcə global pointer dəyişmək modul sərhədini həll etmir.

| Sıra | İş və nəticə | Keçid sübutu | Problem çıxarsa |
|---|---|---|---|
| 0 | Mənbə və artefakt inventarı: stock boot, diaqnostik boot, payload, EFI, kernel, APFS və onların build mənşəyi | Image-dən çıxarılan komponentlərin hash-ləri istifadə edilən mənbə/build ilə əlaqələndirilir | Uyğunsuz artefakt yenidən paketlənir; əvvəlki telefon müşahidəsi yeni image-ə aid edilmir |
| 1 | BootShim → SEC → PEI → DXE → loader → XNU üçün müşahidə planı | Hər sərhədin işarəsi və onu necə oxumaq mümkün olduğu müəyyən edilir | UART/panel yolu məlum deyilsə əvvəl onun pinmux, ünvan və enerji asılılığı araşdırılır; işləməyən vibrator və ya görünməyən yazı mərhələnin keçilmədiyini sübut etmir |
| 2 | Giriş registrləri, exception level, FDT, MMU/cache, reserved-memory, initrd və framebuffer yerləşməsi auditi | Host yoxlamaları interval üst-üstə düşməsini, ölçü daşmasını və səhv FDT-ni rədd edir; son təsdiq canlı handoff tələb edir | Statik xəritə kifayət etmirsə runtime capture hazırlanır; RAM minimum yoxlaması sübutsuz silinmir |
| 3 | Kiçik RAM sistemi ilə XNU-nun bir nüvədə başlanğıcı, timer/interrupt və diaqnostika | Kernel heartbeat, timer irəliləyişi və minimal userspace çıxışı | Xəta ən son təsdiqlənmiş mərhələdə təcrid edilir; storage və iOS image dəyişiklikləri ilə qarışdırılmır |
| 4 | Tam system.apfs üçün RAM-dan asılı olmayan storage yolu | XNU-dan disk bloklarının düzgün oxunması, APFS mount və fayl hash-ləri; bütün image RAM-a köçürülmür | Aşağıdakı storage qərar ağacı tətbiq edilir |
| 5 | iOS 16.5 userland inteqrasiyası: root mount, dyld/cache, launchd, zəruri xidmətlər, yazı tələb edən yollar | launchd və tələb olunan xidmətlər işləyir; çatışmayan syscall/IOKit interfeysi konkret logla göstərilir | Mach-O/ABI, filesystem və xidmət asılılıqları ayrı yoxlanır; uğursuz launchd exec UI uğuru sayılmır |
| 6 | Ekran, compositor/qrafika və touch; saat/enerji tələbləri | Təkrarlana bilən interfeys görüntüsü, toxunmaya cavab, test tətbiqinin açılması | Mövcud software rendering yolunun iOS compositor-a uyğunluğu ayrıca yoxlanır; mümkün deyilsə Mali/IOKit inteqrasiyası əsas bloklayıcı kimi qalır |
| 7 | Quraşdırmaya hazırlıq: təkrar boot, davamlı data, bərpa və sürücü sabitliyi | Sənədləşdirilmiş təkrar sınaqlar, data bütövlüyü, enerji/istilik nəzarəti və təsdiqlənmiş geri dönüş | Daxili yaddaşın bölünməsi təxirə salınır; nasazlıq yaradan komponent düzəldilir və həmin meyar yenidən yoxlanır |

Mərhələ 4-ün host dizaynı mərhələ 1–3 ilə paralel araşdırıla bilər. Onun runtime uğuru əvvəlki CPU və yaddaş sübutlarına bağlıdır. Tam iOS hazır olmadan müşahidə olunan minimal XNU boot-u yoxlamaq üçün bütün sürücülərin bitməsini gözləmək lazım deyil.

## Storage üçün konkret qərar ağacı

Erkən boot müşahidəsi üçün [BOOT-OBSERVABILITY.az.md](BOOT-OBSERVABILITY.az.md) əlavə keçid şərtidir: DEBUG serial çıxışı framebuffer-ə bağlıdır və lookup uğursuzluğunda inicializasiya edilməmiş descriptor istifadəsi əvvəl düzəldilməlidir. Loader payload düzəlişinin ilkin host testləri keçib; bunun ardınca həmin UEFI xəta yolu yoxlanır.

İlk namizəd: mövcud loader block körpüsünün nəqliyyatdan asılı olmayan hissəsini ayırmaq və təsdiqlənmiş microSD/MSDC backend-i ilə oxumaq. Əvvəl ayrıca loader nüvəsi + bir XNU nüvəsi üçün PSCI, MPIDR, cache coherency, DMA və yaddaş sahibliyi yoxlanmalıdır. Tam XNU SMP ilkin tələb deyil, amma ikinci fiziki nüvənin etibarlı işə salınması bu namizəd üçün tələbdir. Qualcomm host-controller registrlərinə toxunan kod bu yola daxil olmamalıdır.

UEFI servislərinin ömrü və loader-in işləməsi saxlanmalıdır; adi ExitBootServices modelini fərz etmək olmaz. XNU-nun controller-i yenidən qurması və loader-in eyni controller-ə müraciəti qarşısı alınmalıdır. Ortaq protokolun versiyası, blok ölçüsü, sərhədlər, timeout və xəta statusu açıq müəyyən edilməlidir.

İlkin oxu mənbəyi mövcud microSD-dəki APFS faylıdır. Fayl backend-i hər sorğunu məhdud buferlə fayl offset-inə çevirməlidir; FAT faylının diskdə ardıcıl olduğu fərz edilmir. Daxili eMMC bölmələrini dəyişmək ilkin dizaynın şərti deyil. Yazılar ilkin olaraq bağlıdır; userland üçün RAM üzərində yazılan data müvəqqəti mərhələdir, davamlı quraşdırma meyarını ödəmir.

Əgər ayrıca nüvədə loader servisi, UEFI storage və ya DMA/cache uyğunluğu təmin edilə bilmirsə, növbəti yol XNU üçün native MTK MSDC block sürücüsüdür. Bu daha böyük işdir: clock/reset, pinmux, regulator, interrupt, timeout və DMA xəta yolları daxildir. Nə bu yol, nə də körpü təsdiqlənibsə, tam iOS storage mərhələsi açıq qalır. Kiçik ramdisk bu problemi həll etmiş sayılmır.

## Araşdırma, yoxlama və növbəti iş

2026-11-05 tarixində açılmış ilkin mənbələr:

- https://github.com/Dracen-W/uefi-merlinx — Redmi Note 9 MT6768 üçün UEFI istinadıdır; A32 board ünvanları və Samsung boot müqaviləsini təsdiqləmir.
- https://github.com/Dracen-W/UniXNU-merlinx — MT6768/6769Z ailəsi üçün müqayisə mənbəyidir; A32-də tam iOS işləməsinin sübutu deyil.

Kod götürülməzdən əvvəl konkret commit, lisenziya, board fərqləri və yerli mənbə ilə diff qeyd olunmalıdır. Samsung/MediaTek kernel mənbələri cihaz ağacı, clock, pinctrl, regulator, MSDC və panel üçün əsas müqayisə mənbəyidir. README iddiaları runtime nəticəsi kimi qəbul edilmir.

Host testləri: boot başlığı/ölçü, payload sərhədləri və checkpoint ayrılması, FDT reserved-memory çıxılması, RAM interval daşmaları, storage sorğularının bounds/timeout davranışı və APFS fayl oxunuşları. QEMU yalnız ümumi kernel/userland/protokol məntiqini yoxlayır, Samsung bootloader və A32 avadanlığını yoxlamır.

İlkin mənbə auditi və ilk patch spesifikasiyası [LOADER-AUDIT.az.md](LOADER-AUDIT.az.md) sənədindədir. Növbəti iş ayrıca A32 volume-first build rejimində payload ownership və real fayl uzunluğu yoxlamalarını tətbiq edib host harness ilə sınamaqdır. Minimal XNU keçidindən əvvəl mövcud GOP tələbi və ya işlək alternativ log kanalı təmin edilməlidir. Storage körpüsü GPT-dən asılı olmayan file backend-i və watch-loop interrupt maskalanması üçün ayrıca yoxlama tələb edir. Display/storage status mətnləri mənbədə mövcudluq ilə cihazda təsdiqi artıq ayırır. Bu nəticələr iOS portunun tamamlanması deyil.
