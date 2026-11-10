# A32 boot müşahidəsi: mənbədə təsdiqlənən asılılıqlar

2026-11-05. Bu audit host mənbələrinə aiddir; cihazın hansı mərhələdə dayandığı hələ məlum deyil.

## İki ayrı çıxış hesab edilən yollar eyni ekrana bağlıdır

A32 DSC → MT6768Pkg → MediaTekPkg → SiliciumPkg include zəncirində DEBUG build üçün `SerialPortLib` olaraq `FrameBufferSerialPortLib`, `DebugLib` olaraq `BaseDebugLibSerialPort` seçilir. Bu konfiqurasiya fiziki UART yaratmır. RELEASE isə null debug/serial kitabxanalarını seçir. Loader-in `put_char` funksiyası lokal RAM loguna və mövcuddursa UEFI `con_out`-a yazır; ayrıca A32 UART implementasiyası burada yoxdur.

Deməli ekranda heç nə görünməməsi həm PEI/debug, həm GOP/loader çıxışını gizlədə bilər. UART alternativi üçün controller, pinmux, saat, baud, elektrik bağlantısı və oxuyucu ayrıca sübut tələb edir. RAM logu yalnız onu əldə edən yol olduqda müşahidə kanalıdır. Daxili logdump-a yazmaq ilkin diaqnostika həlli kimi avtomatik aktiv edilməməlidir.

## Yeni konkret mənbə xətası

İstinad checkout-un `FrameBufferSerialPortLib.c:GetFrameBufferMemory` və `SimpleFb.c:GetFrameBufferInfos` funksiyaları lokal descriptor-u inicializasiya etmir və ardıcıl iki `LocateMemoryRegionByName` çağırışının statusunu yoxlamır. Helper tapmadıqda çıxış parametrini dəyişmir. Hər iki ad tapılmasa stack-dəki naməlum dəyər framebuffer ünvanı kimi istifadə oluna bilər. İkinci adın tapılmaması birinci uğurlu nəticəni silmir; buna görə ikinci lookup-un həmişə framebuffer-i sildiyini demək də yanlış olardı.

Bu, erkən boot üçün xüsusilə vacibdir: PEI patch-i live FDT-ni parse etməzdən əvvəl `DEBUG("MMU In")` çağırır; `Display Reserved` descriptor-u isə live FDT-dəki framebuffer məlumatı uğurla oxunduqdan sonra yaradılır. Beləliklə məhz məlumat olmayan erkən mərhələdə framebuffer debug yolunun təhlükəsiz uğursuz olması lazımdır. Bu kod xətası təsdiqlənib, telefonun logo probleminin səbəbi olduğu təsdiqlənməyib.

## Növbəti düzəlişin şərtləri

1. Hər iki descriptor sıfırlansın, birinci lookup uğursuz olduqda alternativ ad yoxlanılsın; hər ikisi uğursuz olduqda ünvan oxunmadan `EFI_NOT_FOUND` qaytarılsın.
2. Base və length ayrıca qeyri-sıfır, addition overflow olmadan yoxlanılsın. Geometry və handoff oxunmasından əvvəl framebuffer uzunluğu kifayət etməlidir; `FbBase + FbLength - FB_HANDOFF_OFFSET` kiçik uzunluqda underflow edə bilər.
3. DEBUG printer öz uğursuzluğunu yenidən DEBUG ilə yazmasın; rekursiya yaranmamalıdır. Framebuffer yoxdursa sıfır bayt qaytarması normaldır, boot uğuru kimi təqdim edilmir.
4. Düzəliş ayrıca A32 UEFI patch-i olsun; `apply.sh` pinned base yoxlamasını və təkrar tətbiqdə reverse-check davranışını bütün patch-lər üçün saxlasın. İstinad checkout-da əl ilə untracked dəyişiklik tək həll sayılmasın.
5. Host testləri: birinci ad, yalnız alternativ ad, hər ikisi yoxdur, sıfır base/length, overflow, kiçik handoff regionu. Sonra DEBUG UEFI build. Bu testlər görüntünün real paneldə işlədiyini sübut etmir.

## Ekran yolunun növbəti keçid meyarı

A32 memory parser `/chosen` daxilində `atag,videolfb-fb_base_h`, `atag,videolfb-fb_base_l`, `atag,videolfb-vramSize` gözləyir. Bunlar yoxdursa mövcud parser display descriptor-u yaratmır. SimpleFb isə build-dəki 1080×2400, 32-bit və stride=width fərziyyələrindən istifadə edir. Live LK scanout bazası, formatı, stride-ı və ayrılmış sahənin tutumu yoxlanmalıdır; vramSize mövcudluğu təkbaşına bu fərziyyələri sübut etmir.

İlk müşahidə meyarı: təhlükəsiz framebuffer girişindən sonra sabit görünən mərhələ işarəsi. Bu alınmırsa fiziki UART və ya təsdiqlənmiş başqa əldəetmə kanalı tələb olunur. Bu kanal müəyyənləşənədək yeni cihaz boot cəhdi hazır hesab edilmir. Host payload, FDT və storage işləri bu vaxt davam edə bilər.

## Tətbiq və yoxlama nəticəsi

`0002-framebuffer-region-validation.patch` hər iki descriptor-u sıfırlayır, lookup statuslarını yoxlayır və alternativ adı yalnız birinci uğursuz olanda sınayır. Sıfır ünvan/uzunluq və interval overflow rədd edilir; serial yolunda handoff offset-indən kiçik region da rədd edilir. `apply.sh` bütün A32 patch-lərini pinned base üzərində tətbiq edir; iki ardıcıl tətbiq uğurla keçdi.

`python3 devices/a32/tools/test-framebuffer-lookup.py` staged production funksiyalarını çıxarıb host stubları ilə sınadı: birinci ad, alternativ ad, yoxdur, sıfır base, sıfır length, overflow və kiçik region. Hər iki funksiyada 7 ssenari keçdi. Kiçik regionun GOP tərəfindən hələ qəbul edilməsi testdə açıq göstərilir: bu patch geometry capacity yoxlaması deyil. Handoff-un içindəki base/stride/height və ekranın əsl scanout məlumatı növbəti işdir.

`devices/a32/uefi/build-local.sh` DEBUG build-i uğurla bitirdi (32 saniyə). Build logu `/tmp/a32-framebuffer-build.log` faylındadır. FVMAIN-də 2,672 bayt boş yer qalıb; xarici sıxılmış 3 MiB firmware volume-da daha çox yer olması daxili volume-a yeni sürücülərin sərbəst əlavə edilə biləcəyini göstərmir. Növbəti modul əlavəsində daxili FV tutumu ayrıca yoxlanmalıdır. Telefon və yeni boot image sınağı aparılmayıb.

### Geometry düzəlişi

`0003-framebuffer-geometry-bounds.patch` debug yazısından əvvəl base, stride, width/height və ümumi pixel intervalını yoxlayır. Son 64 bayt cursor/handoff üçün saxlanır; metadata ilə üst-üstə düşən görüntü rədd edilir. Sıfır font miqyası və bir simvol yerləşməyən ölçü rədd edilir. Naməlum cursor X/Y dəyərləri piksel offset-i kimi istifadə edilməzdən əvvəl sıfırlanır; freeze marker saxlanır. GOP yolunda rəng dərinliyi, sahəyə yerləşmə və mövcud 32-bit ölçü hesabının daşması yoxlanır.

Host testi artıq 7 lookup və 9 geometry ssenarisini keçir. Tam rendering, handoff record-un real firmware tərəfindən hazırlanması və ekran scanout-u bu testin əhatəsində deyil. DEBUG UEFI build yenidən uğurludur (`/tmp/a32-geometry-build.log`). FVMAIN avtomatik 0x336000-dan 0x337000-a böyüdü; əvvəlki az boşluq rəqəmi təkbaşına sərt tutum limiti kimi yozulmamalıdır. Son build-də istifadə 0x336f90, xarici compact volume istifadə 667,680 baytdır.

Əlavə auditdə `Sec.c:ClearFrameBuffer` funksiyasında da ilkinizasiya olunmamış descriptor və yoxlanmayan lookup-lar tapıldı. Oradakı bütöv regionu sıfırlama əməliyyatı ayrıca düzəldilməlidir; əvvəlki iki lookup düzəlişi bütün framebuffer istifadəçilərini təhlükəsiz etmiş sayılmır. Növbəti iş həmin çağırışı və digər framebuffer lookup istifadəçilərini tam inventarlaşdırmaq, sonra SEC üçün ayrıca patch/test əlavə etməkdir.

### SEC düzəlişi və inventarın nəticəsi

`0004-sec-framebuffer-clear-validation.patch` əlavə edildi. SEC clear descriptor-u sıfırlayır, lookup uğursuz olduqda yaddaşa toxunmur, sıfır və overflow intervalını rədd edir. Eyni host harness SEC funksiyasını da çıxarıb saxta `ZeroMem` ilə nə vaxt və hansı intervala yazı istəndiyini yoxlayır: 7 SEC ssenarisi keçdi. Cari cəm: 7 lookup + 9 geometry + 7 SEC ssenarisi. UEFI DEBUG build uğurludur (28 saniyə, `/tmp/a32-sec-build.log`). Bu testlər həqiqi RAM xəritəsinin düzgünlüyünü təsdiqləmir.

Silicon ağacındakı `Display Reserved`/`Display_Reserved` axtarış istifadəçiləri inventarlaşdırıldı: serial debug, SimpleFb GOP və SEC clear. Bu üç istifadəçi patch dəstində əhatə olunur. Platformalara məxsus statik region cədvəlləri başqa cihazların məlumatıdır; A32 üçün sübut kimi götürülmür.

İki mühüm qalıq asılılıq:

- `PrintFirmwareVersion` daxilində clear live FDT parsing-dən əvvəl çağırılır. A32-də o anda display region yoxdursa təhlükəsiz skip edilir. Buna görə handoff header-dəki “SEC hər restart-da bu regionu sıfırlayır” şərhi A32 üçün təminat deyil. Geometry guard sərhəddən çıxmanı bloklayır, lakin köhnə, sərhəd daxilində görünən handoff-un həqiqi scanout olması ayrıca təsdiq tələb edir.
- `MT6768Pkg/Library/PlatformSecLib/PlatformSec.c` watchdog-u söndürür və `Display OVL + 0x44` registrində BIT28-i qurur. Lookup statusu burada yoxlanır, amma həmin əməliyyatın Samsung panel pipeline-ına uyğunluğu hələ sübut olunmayıb. Yeni panel əmrləri əlavə etməzdən əvvəl bu miras davranış Samsung mənbəyi ilə müqayisə edilməlidir.

BootShim mənbəsində x0 dəyişdirilmir və SEC-ə saxlanaraq gedir; bu mənbə faktı LK-nin x0-da düzgün FDT verdiyinin runtime sübutu deyil. Relocation scratch ünvanı `FD_BASE + FD_SIZE + 0x70000` olur; onun live yaddaşla ziddiyyətsizliyi ayrıca yoxlanmalıdır. Növbəti əsas audit boot giriş müqaviləsi və live FDT etibarlılığıdır, daha çox görünməyən debug mesajı əlavə etmək deyil.
