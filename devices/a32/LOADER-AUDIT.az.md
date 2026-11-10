# Loader auditi və ilk dəyişikliklərin spesifikasiyası

2026-11-05. Mənbə səviyyəli baxışdır; telefonun hazırkı nasazlığının səbəbini təsdiqləmir. Sətirlər həmin tarixdəki lokal, dəyişdirilmiş `xnuloader/loader.c` faylına aiddir.

## Payload əldə etmə və ömrü

`efi_main:4452` əvvəlcə `0xF0000000` ünvanındakı magic-i oxuyur. Yalnız bundan sonra `load_payload_from_volume:4313` həmin ünvanda 64 MiB ayırmağa çalışır. Exception hook isə daha gec quraşdırılır. Beləliklə ilk oxunuşun təhlükəsizliyi həmin ünvanın firmware tərəfindən xəritələnmiş olmasına bağlıdır; proqram bunu əvvəlcədən təmin etmir. Bu mənbədə təsdiqlənmiş şərtdir, cihazda exception baş verdiyinin sübutu deyil.

Təkcə ilk oxunuşu dəyişmək kifayət deyil: allocation/read uğursuz olsa belə banner-in `payload_text_entry:4389` funksiyası və `parse_payload:2574` eyni ünvanı oxuyur. Parser regionun maksimum tutumuna əsaslanır, həqiqətən oxunmuş fayl uzunluğuna yox. Nəticədə düzgün magic və yanlış header ölçüsü olan fayl üçün fayldan kənar, ayrılmış amma doldurulmamış baytlar təhlilə düşə bilər.

Dinamik ünvana keçid üçün bütün asılılıqlar birlikdə yenilənməlidir: parser, banner/platform mətni, USB download, `choose_window` istisna intervalı və son 1 MiB-dəki panic log. Yalnız allocation ünvanını dəyişmək parçalanmış vəziyyət yaradar. İlkin düzəliş dinamik relocation-dan əvvəl ownership və etibarlı uzunluq modelini qurmalıdır.

İlk patch-in müqaviləsi:

1. Payload vəziyyəti `absent/owned/validated` kimi açıq izlənir; base, ayrılmış capacity və etibarlı bytes ayrıca saxlanır. XNUP wire formatı dəyişmir.
2. A32-nin filesystem boot rejimi payload məzmunundan əvvəl məlum olmalıdır: ayrıca build seçimi və ya firmware-dən açıq handoff. Payload içindəki `platform=a32` bu ilkin qərar üçün istifadə oluna bilməz, çünki onu oxumaq üçün əvvəl payload lazımdır. İlkin seçim ayrıca A32 loader build variantıdır; QEMU/preloaded yoluna toxunmadan volume-first rejimi seçir.
3. Volume-first variant magic-i allocation-dan əvvəl oxumur. Uğursuz allocation/read nəticəsində parser və banner payload-a müraciət etmir; diaqnostik səbəb göstərilir və kernel başlanmır. Platforma A32 kimi qalır, QEMU fallback-i olmur.
4. Header və hər entry-nin padded ölçüsü etibarlı bytes daxilində yoxlanır. Natamam, ölçüsü daşan və lazımi mətn terminatoru olmayan girişlər rədd edilir. Uğursuzluqda state sıfırlanır və yalnız həqiqətən ayrılmış region azad edilir.
5. Preloaded QEMU/telefon yolu ayrıca saxlanır; onun giriş müqaviləsi və regionun kim tərəfindən rezerv edildiyi sənədləşdirilir. Ümumi loader-də bütün platformaları kor-koranə volume-first etmək olmaz.

Host qəbul testləri: allocation failure; yoxdur/qısa fayl; yarımçıq read; magic səhvi; header-in real fayldan böyük olması; entry truncation və padding sərhədi; valid A32 payload; legacy preloaded fixture. Bunlar üçün EFI allocation/file əməliyyatları stub edilən harness istifadə edilməlidir; A32 avadanlığını simulyasiya etdiyi iddia edilməməlidir. Ayrılmış yaddaşdan əvvəl və free-dən sonra oxunuş olmadığını harness izləməlidir.

## Storage körpüsünün əlavə asılılıqları

`block_start:1904` partition-info tapılmasa çıxır və yalnız GPT tipli partition-ları əlavə edir. Buna görə FAT32 microSD-də APFS faylı mövcud olması həmin faylın XNU block cihazı kimi görünməsi demək deyil. Yeni file backend ayrıca qeydiyyatdan keçməli, GPT aşkarlanmasından asılı olmamalıdır.

`block_poll:2120` core-0 gözləmə dövründən çağırılır. Bu dövr bir müddət sonra interrupt-ları maskalayır (`watching_only`). MSDC/file I/O interrupt tələb edirsə, əvvəl işləyən oxu bu keçiddən sonra dayana bilər. Testlər həm erkən, həm maskalanmadan sonrakı I/O-nu əhatə etməlidir. Polling ilə işləyən backend sübut olunmasa mövcud watch-loop modeli qəbul edilmir.

`drivers/storage/hakios.ufs.c` artıq mutex ilə tək sorğu, bölünmüş transfer və 20 saniyəlik timeout ehtiva edir. Bunları yenidən ixtira etmək əvəzinə generic körpüyə ayrılan hissədə qorumaq, timeout-dan sonra gec cavab/bufer sahibliyini yoxlamaq lazımdır. Native UFS register yolu və Qualcomm controller ownership yoxlaması generic backend-dən ayrılmalıdır.

Əlavə qəbul testləri: MBR/FAT və GPT-dən asılı olmayan fayl backend-i; parçalanmış faylda offset oxunuşu; son blok və out-of-range; short read; media removal; gec cavab; maskalanmış interrupt vəziyyətində oxu; kernel və loader cache görünürlüğü. Backend read failure kernelə xəta qaytarmalıdır, köhnə buferi uğurlu məlumat kimi təqdim etməməlidir.

## Boot müşahidəsində daha bir keçid şərti

`efi_main:4508` ətrafında A32 üçün GOP yoxdursa kernel handoff-dan əvvəl reboot edilir. Buna görə hazırkı loader ilə planın minimal XNU mərhələsi də GOP-a bağlıdır. İki yol var: firmware GOP-u təsdiqləmək və ya ayrıca sübut olunmuş serial/memory-log oxuma kanalı qurulduqdan sonra yalnız diaqnostik build üçün headless handoff əlavə etmək. Sadəcə GOP yoxlamasını silmək müşahidəsiz yeni boot cəhdi yaradar və qəbul edilmir.

İcra sırası: payload ownership/bounds patch-i və host harness → loader-in erkən diaqnostika çıxışı → GOP/alternativ müşahidə qərarı → minimal XNU → ayrı nüvə və storage backend. Payload patch-i RAM tutumu, GOP və ya Samsung logo problemini avtomatik həll etmiş sayılmır.

## Paketləmə hazırlığı — görülən iş

`tools/verify-payload.py` əlavə edildi və `uefi/package-bootimg.sh` loader build-dən əvvəl onu çağırır. XNUP real uzunluğu, entry/padding sərhədləri, mətn terminatorları, duplicate entry, A32 platforması və kernel mövcudluğu yoxlanır. `EXPECTED_CHECKPOINT=998` kimi açıq seçim paketləmədə gözlənilən mərhələni tələb edir; seçim yoxdursa mövcud mərhələ hesabatda göstərilir. Bu yoxlama kernel-in Mach-O uyğunluğunu və ya boot qabiliyyətini təsdiqləmir.

Lokal `out/a32/a32-payload.bin` yoxlamadan keçdi: 18,541,200 bayt, checkpoint 0, SHA-256 `80c978dd319e1eca40709bccff7f9233cab72c3f15741c55a7b25fa032dfd516`. Bu ayrıca host faylıdır, əvvəlki hold image-in daxilindəki checkpoint 998 payload ilə eyniləşdirilməməlidir. Valid fixture və 10 səhv giriş ssenarisi yoxlanıldı; shell sintaksis yoxlaması keçdi. Paketləmə, build və cihaz sınağı icra edilmədi. Runtime loader ownership/bounds düzəlişi hələ açıqdır.

## Sonrakı irəliləyiş: ilkin runtime düzəlişi

`xnuloader/build.sh --a32` ayrıca `loader-a32.efi` yaradır; A32 paketləyicisi məhz bu variantı build edib götürür. `A32_VOLUME_FIRST` rejimi əvvəlcə volume load edir, `payload_readable` isə uğursuz allocation/read zamanı banner və parser oxunuşlarını bloklayır. Platforması A32 olmayan və ya yüklənməmiş payload kernel handoff-a buraxılmır. Ümumi build preloaded giriş müqaviləsini saxlayır.

Fayl yükləmə yolunda `volume_payload_valid` real fayl ölçüsünü, entry/padding sərhədlərini və parser-in istifadə etdiyi mətnlərin sonlandırılmasını yoxlayır. Yalnız bundan sonra payload oxuna bilən elan edilir. Bu ilkin patch sabit ünvanı dinamik etmir və legacy preloaded/USB girişini tam sərtləşdirmir. C validator host verifier-dən daha dar siyasətə malikdir: duplicate entry və daxili NUL kimi semantik yoxlamaların eyniləşdirilməsi açıqdır.

A32 EFI build uğurludur: 75,776 bayt. Sistem clang və lokal LLVM 18 lld-link istifadə edildi; əvvəlki link cəhdi PATH-də lld-link olmadığına görə dayanmışdı. Production C validator mənbədən çıxarılaraq host kitabxanası kimi yığıldı: real payload qəbul edildi, 6 səhv/boş giriş rədd edildi. Tam EFI allocation/read failure harness-i, legacy build regression və diaqnostika çıxışının runtime yoxlanması hələ tamamlanmayıb. Boot image paketlənmədi və cihaz əməliyyatı olmadı.

Sonrakı yoxlama: `python3 devices/a32/tools/test-loader-volume.py` production load/text funksiyalarını EFI stub-ları ilə işlədir. Ayrılmadan əvvəl və free-dən sonra region `PROT_NONE` olur. 8 ssenari (uğurlu hissəli read, allocation failure, file yoxdur, qısa info, read error, zero read, həddən artıq qaytarılan read ölçüsü, yanlış payload uzunluğu) keçdi; close/free sayları yoxlandı. Bu test bütün `efi_main`, ARM kodu və firmware davranışını əhatə etmir. Ümumi loader ayrıca `/tmp` artefaktlarına compile/link edildi; bu build regression yoxlamasıdır, QEMU runtime sınağı deyil. Erkən çıxış auditi [BOOT-OBSERVABILITY.az.md](BOOT-OBSERVABILITY.az.md) sənədində davam edir.
