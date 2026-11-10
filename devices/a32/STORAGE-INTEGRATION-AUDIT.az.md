# A32 storage inteqrasiyası — 2026-11-10

## Build nəticəsinin düzəlişi

Əvvəlki checkpoint symbolset xətalarını kernel build bloklayıcısı kimi təqdim edirdi.
Bu nəticə natamam jurnal oxunuşuna əsaslanırdı. `tools/make-kernel.sh` bu konfiqurasiyada
kext export yoxlamalarının uğursuzluğunu ayrıca təsnif edir; kernel linkini qəbul edir.
Bu yoxlamalar düzəldilmədi və söndürülmədi. Kext uyğunluğu təmin olundu iddiası yoxdur.

Təzə build: wrapper exit 0, daxili make exit 2. İlk iki çağırış inkremental idi;
`-W` ilə çağırış storage obyektlərini yenidən kompilyasiya etmədi. Sonra yalnız staged
`bsd/dev/hakios.ufs.c` və `hakios.ufshc.c` fayllarının mtime-ı touch ilə yeniləndi
(məzmun dəyişmədi). Son jurnal **CC hakios.ufs.o**, **CC hakios.ufshc.o**, **CC version.o**,
**LD mach.development.bcm2837.unstripped** göstərir. Son kernel: 14406696 bayt, SHA-256 `a10adf30416df3026e98455b8aa39a0519c5ae567379b210dfe1c0397d1e0408`.
`_hakios_ufs_init`, `_ufs_read_mailbox`, `_ufshc_probe` binarda var. Native sürücü də
link olunur; bu, aktivləşdirildiyi demək deyil.

## Müqavilə və parametrlər

Production loader və kernel struct-ları birbaşa çıxarılıb bütün istifadə olunan sahələrin
ölçü/offset-ləri, struct ölçüləri və protokol sabitləri static assert ilə müqayisə edildi.
`aarch64-unknown-windows` və `arm64-apple-ios16.5` hədəflərində keçdi. Consumer layout-u
qəsdən dəyişdirilmiş mənfi nəzarət compile zamanı rədd edildi. Bu test cache coherency,
SMP, fiziki mapping və real I/O-nu yoxlamır.

Cari `.config` üçün `hakios-config.py check` keçir; `args` yalnız `ufs=2` verir.
`CONFIG_HAKIOS_UFS=y`; native/write arqumentləri yoxdur. Kernel init yalnız `ufs_shared_pa`
olduqda işə düşür; native controller probe ayrıca `ufs_native` tələb edir.

## Real növbəti maneələr

1. `xnuloader/loader.c`: `block_poll()` çağırışları yalnız `run_on_other_cpu()` daxilindədir.
   `kernel_mpidr` default olaraq loader-in cari nüvəsidir; yalnız `bootcpu=` onu dəyişir.
   Cari config args belə seçim vermir. Eyni nüvədə `jump_to_kernel()` zamanı mailbox-u
   cavablandıran loader watch loop işləmir. Deməli, yalnız `ufs=2` əlavə etmək xidməti işlək etmir.
   A32 platform profile `.cores=1, .core_shift=0` daşıyır; bu fiziki nüvə sayı barədə ölçmə deyil.
   Fərqli nüvənin MPIDR/PSCI/interrupt/timer müqaviləsi hələ təsdiqlənməyib.
2. `out/a32/a32-payload.bin` kanonik verifier-dən keçir, checkpoint default 0-dır,
   amma **cmdline entry yoxdur** (nə `ufs=2`, nə `root_apfs`, nə `bootcpu`).
   İçindəki kernel hash-i yeni `hakios-kernel` ilə fərqlidir. Köhnə payload dəyişdirilmədi.
3. Kernelin APFS mount etməsi, firmware-in microSD-ni açması və XNU bootu sübut edilməyib.

Növbəti iş: eyni nüvədə işləməyən storage konfiqurasiyasını host regression testi ilə
rədd edən handoff guard-ını hazırlamaq; sonra A32 ikinci nüvə/PSCI müqaviləsini mənbə və
mövcud firmware sübutları ilə araşdırmaq. Sadəcə `bootcpu=1` yazmaq sübut edilmiş həll deyil.
Yeni payload hazırlamaq ayrıca addımdır; config dəyişməsi mövcud payload-u avtomatik yeniləmir.

## Sübutlar

`out/a32/kernel-storage-2026-11-10/`: `storage-recompile.out`, `xnu-storage-recompile.log`,
`kernel-symbols.txt`, `storage-abi.c`, iki `abi-*.log`, `abi-mutation.log`,
`payload-texts.json`, `evidence.json`. ABI harness yalnız host analiz artefaktıdır.
Bu sessiyada production mənbə dəyişikliyi, telefon əməliyyatı, flash və unlock olmadı.
