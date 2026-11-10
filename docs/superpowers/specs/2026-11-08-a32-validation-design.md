# A32 yoxlama və düzəliş dizaynı

Status: istifadəçi 2026-11-08 tarixində təsdiqləyib. İlkin payload mərhələsi və ondan sonrakı real-libfdt
yaddaş-xəritəsi mərhələsi tamamlanıb (`devices/a32/tools/test-loader-volume.py` 21 ssenari;
`devices/a32/tools/test-memory-map-fdt.py` 14 real-libfdt ssenarisi). Storage/fayl-backend və cihaz
runtime sübutu hələ açıqdır; `devices/a32/IOS-INSTALL-BLOCKERS.az.md` cari vəziyyəti saxlayır.

## Məqsəd

A32 portundakı sübut edilən xətaları ardıcıl aradan qaldırmaq, host nəticəsini cihaz nəticəsindən ayırmaq və müşahidə edilə bilən UEFI → loader → minimal XNU sınağına çatmaq. Tam iOS üçün storage, sürücülər və userland ayrıca mərhələlərdir; heç bir məhdud test dəsti bütün mümkün xətaların yoxluğunu sübut etmir.

## Cari sübut

2026-11-08 tarixli canlı read-only probe SM-A325F / A325FXXSCDXL2, `sys.boot_completed=1`, `flash.locked=1`, verified boot `green`, vbmeta state `locked` qaytardı. `/chosen` altında paket və split framebuffer property adlarının hamısı mövcuddur. Dəyərlər və fb0 stride/geometry oxunuşları icazə xətası verdi. `adb exec-out` bu xəta mətnini sıfır exit-code ilə qaytardı; çıxış valid FDT property-si sayılmır.

Sübut faylları: `out/a32/readiness-2026-11-08/device-checks.json`, `out/a32/live-probe-2026-11-08.json`. Beş mövcud host test skripti təkrar uğurla keçdi. Mövcud payload `--checkpoint 0` yoxlamasına ayrıca verildi; onun nəticəsi sessiya çıxışında saxlanır.

## Yanaşmalar və seçim

1. Host sübutu → təkrarlanan xəta testi → minimal düzəliş → build → mümkün olduqda cihaz testi. Tövsiyə edilən və indiki vəziyyətdə icra edilə bilən yol budur. Məlumatları qoruyur və xətanın hansı mərhələdə olduğunu ayırır.
2. Ekranın stride/base dəyərlərini fərz edib təkrar flash. Real LK müqaviləsi və unlocked vəziyyət olmadığı üçün qəbul edilmir.
3. Storage/Mali/touch daxil olmaqla bütün platformanı bir dəyişiklikdə tamamlamaq. Erkən boot sübutu yoxdur; nəticənin səbəbini təcrid etmək mümkün deyil. Bu işlər erkən boot keçidindən sonra ayrıca planlanır.

İstifadəçi tövsiyə edilən dizaynı təsdiqləyib. Mövcud mənbə və uncommitted iş saxlanacaq, avtomatik commit edilməyəcək.

## İlk implementasiya: payload yoxlamasının semantik sərhədi

`devices/a32/tools/verify-payload.py:inspect` duplicate adları, adın NUL-dan sonrakı qeyri-sıfır baytlarını, data padding-i və mətnin daxili NUL-larını rədd edir. `xnuloader/loader.c:volume_payload_valid` hazırda bu qaydaların hamısını tətbiq etmir. Bu, mənbədə görünən yoxlama fərqidir; onun real pis fixture-ni qəbul etməsi düzəlişdən əvvəl çalışan testdə göstərilməlidir. Bu iş Samsung bootloader kilidini və ya ekran stride-ını düzəltmiş sayılmayacaq.

İlk işin məqsədi struktur və mətn kanonikliyini uzlaşdırmaqdır. A32 platforma/kernel tələbi ilə generic preloaded/QEMU siyasəti eyniləşdirilməyəcək. Checkpoint rəqəminin runtime diapazonu və UTF-8 qaydaları ayrıca mövcud parser-lə yoxlanmalıdır; sübutsuz “tam parity” iddiası olmayacaq. Yeni memory allocation və kvadratik duplicate-scan üçün sərhədsiz xərc qəbul edilmir; mövcud formatın genişlənmə qaydası nəzərə alınmalıdır.

### Təsdiqə təqdim edilən test sərhədləri

| Sərhəd | Yoxlanacaq davranış | Sübut etmədiyi |
|---|---|---|
| Host `inspect(bytes)` | normal payload qəbul edilir; duplicate, noncanonical ad/terminator/padding, daxili NUL rədd edilir | UEFI fayl I/O və ARM execution |
| Mövcud host harness-də production volume load → payload visibility | eyni malformed fixture parser/banner-ə görünən olmur; allocation/file cleanup saxlanır | Samsung bootloader image qəbulu |
| A32 və generic EFI build | yeni qaydalar hər iki variantda compile/link edilir; mövcud legacy yolu saxlanır | QEMU və ya telefon runtime uğuru |

TDD qaydası: hər dəfə bir malformed fixture → gözlənilən səbəbdən qırmızı nəticə → minimal production düzəlişi → yaşıl nəticə və əvvəlki testlər. Stublar yalnız EFI sərhədindədir; validation məntiqinin test surəti yazılmır. Yeni testlər bu sərhədlərin təsdiqindən sonra yazılır.

## Sonrakı mərhələlər

1. Real libfdt üzərindən binar DTB fixture-ləri ilə production memory-map girişini yoxlamaq: malformed lengths, missing properties, reservations/overlap, display bounds. Hazırkı stubların yerinə gerçek traversal sübutu lazımdır. Host fixture telefondan capture edilmiş kimi təqdim edilməyəcək.
2. Dəqiq stock LK/live handoff üzrə base, stride, format, layer və erkən RAM ownership müəyyənləşdirmək. Cari Android property adlarının mövcudluğu dəyər, fiziki əlçatanlıq və UEFI girişindəki x0 demək deyil.
3. Güvənilən erkən mərhələ müşahidəsi, sonra minimal XNU/timer/interrupt. İkinci nüvə və storage yolu bundan sonra ayrıca dizayn edilir.
4. Tam APFS üçün disk-backed storage; sonra userland, qrafika/touch və davamlı məlumat. Əvvəlki RAM tutumu bloklayıcısı açıq qalır.

## Cihaz testinin şərtləri

Read-only Android testlərinə cari tapşırıq icazə verir və ilkin testlər artıq aparılıb. Eksperimental firmware boot hazırda kilidli cihazda icra edilə bilən yol deyil. Bootloader unlock, data wipe, relock və repartition bu dizaynın əməliyyatları deyil. Bunlardan hər hansı biri həqiqətən tələb olunarsa konkret nəticəsi və bərpa addımları istifadəçiyə əvvəlcədən göstərilməlidir. Rəsmi boot artefaktı və hash-i saxlanılır.

## Qəbul meyarı və hesabat

İlk mərhələnin qəbul meyarı: yeni testin əvvəl həqiqi fərqi göstərməsi, düzəlişdən sonra keçməsi, beş mövcud testin yaşıl qalması, A32/generic build-in uğuru və dəyişiklik sərhədlərinin baxışı. Telefon runtime sınağı ayrıca `keçdi / uğursuz / icra edilə bilmədi` kimi qeyd edilir. `Permission denied` və locked cihaz nəticələri uğurlu firmware testi sayılmır.

Mövcud no-delegation seçimi saxlanır: iş və ilkin review bu sessiyada bir agent tərəfindən aparılır. Yeni implementasiya planı bu dizayn təsdiqləndikdən sonra `superpowers:writing-plans` ilə hazırlanacaq.
