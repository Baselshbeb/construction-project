> Bu sayfa Turkce cevirisidir. [English version](../accuracy-and-limitations.md)

# Dogruluk ve Sinirliliklar

Metraj, insaat profesyonellerine malzeme tahmini konusunda yardimci olan bir aractir. Bu belge, sistemin neleri iyi yaptigi, sinirliliklarinin nerede oldugu ve ciktinin dogrulanmasi icin hangi adimlarin atilmasi gerektigi konusunda durust bir degerlendirme sunar.

---

## Dogruluk IFC Model Kalitesine Baglidir

Tahmin dogrulugundaki en onemli faktor, girdi IFC dosyasinin kalitesidir. Metraj yalnizca modelde mevcut olan verilere dayanarak malzeme tahmini yapabilir.

### Yuksek Dogruluk Senaryolari

Metraj, asagidaki durumlarda en guvenilir tahminlerini uretir:

- BIM modeli, onceden hesaplanmis alanlar, hacimler ve uzunluklar saglayan **miktar setleri** (Qto) etkinlestirilerek disa aktarilmissa
- Duvarlarda **IsExternal** ozelligi ayarlanmissa, boylece dis ve ic duvarlar dogru sekilde ayirt ediliyorsa
- Modeldeki elemanlara **malzemeler** atanmissa (orn. bir duvarda "Beton C25/30")
- Elemanlar dogru sekilde **katlara** atanmissa
- Genel geometri yerine standart eleman turleri (IfcWall, IfcSlab, IfcColumn vb.) kullanilmissa

### Dusuk Dogruluk Senaryolari

Asagidaki durumlarda dogruluk azalir:

- Miktar setleri yoksa (Metraj, miktarlari temel boyutlardan turetir; bu, karmasik sekilller icin yaklasik bir degerdir)
- IsExternal ozelligi eksikse (yapay zeka siniflandiricisi eleman adi ve konumuna gore tahmin yapar)
- Malzeme atamalari yoksa (yapay zeka varsayilan malzeme kabullerini kullanir)
- Elemanlar belirli turler yerine genel vekil nesneler (`IfcBuildingElementProxy`) olarak modellenmisse

---

## Bilinen Sinirliliklar

### Egri ve Karmasik Geometri

Metraj'in miktar hesaplayicisi, IFC dosyasindaki boyutsal ozellikler (uzunluk, yukseklik, genislik) ve onceden hesaplanmis miktarlar (alan, hacim) ile calisir. Egri duvarlar, daralan elemanlar veya karmasik geometri icin hesaplayici, yalnizca temel boyutlardan miktarlari dogru sekilde turetmeyebilir. BIM aracindan gelen onceden hesaplanmis miktar setleri bunu dogru sekilde halleder.

### MEP Desteklenmiyor

Mekanik, elektrik ve tesisat elemanlari su anda desteklenmemektedir. `IfcDistributionElement`, `IfcFlowSegment` ve `IfcFlowTerminal` gibi IFC elemanlari taninen eleman listesinde yer almaz. MEP miktarlari ayri olarak tahmin edilmelidir.

### Donati Tahminidir

Donati celigi miktarlari, sektorde standart kg/m3 oranlari kullanilarak tahmin edilir:

| Eleman | Celik Orani |
|---|---|
| Temeller | 60-80 kg/m3 |
| Duvarlar (yapisal) | 60-80 kg/m3 |
| Dosemeler | 80-120 kg/m3 |
| Kolonlar | 130-180 kg/m3 |
| Kirisler | 100-150 kg/m3 |

Gercek donati miktarlari, tipik bir IFC modelinde bulunmayan yapisal analize (yuk durumlari, acikliklar, deprem gereksinimleri) baglidir. Tahminler butceleme icin uygundur ancak yapisal cizimlere karsi dogrulanmadan donati siparisi icin kullanilmamalidir.

### Fire Paylari Sektor Ortalamalarindan Alinmistir

Uygulanan fire paylari genel sektor ortalamalarindir. Gercek fire, asagidaki faktorlere gore onemli olcude degisir:

- Yapi yontemi (prefabrik ile yerinde dokum karsilastirmasi)
- Isclik beceri duzeyi
- Santiye kosullari (erisim, hava durumu)
- Malzeme kalitesi ve tedarik zinciri
- Proje olcegi

Tam tablo ve ozellestirme talimatlari icin [Fire Paylari Referansi](../../reference/waste-factors.md) belgesine bakin.

### Yapay Zeka Hata Yapabilir

Uc boru hatti asamasi karar verme icin Claude AI kullanir:

- **Siniflandirma:** Yapay zeka, olagan disi veya belirsiz durumlarda elemanlari yanlis kategorize edebilir
- **Malzeme eslestirme:** Yapay zeka malzemeleri kacirabilir, yanlis malzemeler onerebilir veya yanlis carpanlar kullanabilir
- **Dogrulama:** Yapay zeka incelemesi, gercek olmayan sorunlari isaretleyebilir veya gercek sorunlari kacirabilir

Tum yapay zeka kararlari nitelikli bir profesyonel tarafindan incelenmelidir. Yapay zekanin ne yaptigina ve hatalarin nasil ele alindigina iliskin ayrintilar icin [Yapay Zeka Seffafligi](../../architecture/ai-transparency.md) belgesine bakin.

### Birim Fiyat Sinirliliklari

Metraj yalnizca miktarlari olusturur -- birim fiyatlari icermez. Keşif cetvelindeki Birim Fiyat ve Tutar sutunlari, kullanicinin guncel piyasa fiyatlariyla doldurulmasi icin bos birakilir.

### Gecici Isler

Gecici insaat isleri (iskele, destek, su bosaltma, santiye ofisleri) tahmin edilmez. Yalnizca tamamlanmis yapinin parcasi olan kalici malzemeler dahil edilir.

### Kaplamalar ve Donanimlar

Detayli kaplama sartnameleri (fayans desenleri, boya sistemleri, asma tavan turleri) yalnizca ilgili elemanlar IFC dosyasinda modellenmisse tahmin edilir. Genel kaplama karsiliklari otomatik olarak eklenmez.

### Sahaya Ozgu Kosullar

Sistem, asagidaki gibi sahaya ozgu kosullari dikkate almaz:

- Temel tasarimini etkileyen zemin kosullari
- Deprem bolgesi gereksinimleri
- Yangin dayanim gereksinimleri (IFC ozelliklerinde bulunanlar haricinde)
- Yerel yapi yonetmeligi gereksinimleri
- Yapi yontemini etkileyen erisim kisitlamalari

---

## Dogrulama Sonuclari

Her metraj, iki seviyeli kontrol iceren bir dogrulama raporu icerir:

### Aritmetik Kontroller (8 kontrol)

Bunlar deterministik ve guvenilirdir:

1. IFC dosyasindan elemanlar ayristirildi
2. Elemanlar kategorilere siniflandirildi
3. Miktarlar hesaplandi
4. Malzemeler eslestrildi
5. Negatif miktar yok
6. Beton orani makul (doseme alani basina 0.1-1.5 m3/m2)
7. Tum katlarda en az bir eleman var
8. Celik-beton orani makul (50-200 kg/m3)

"8/8 BASARILI" sonucu, tum aritmetik kontrollerin gectigini gosterir. Bu, dogrulugu garanti etmez -- acikca imkansiz degerlerin tespit edilmedigini ifade eder.

### Yapay Zeka Muhendislik Incelemesi

Yapay zeka incelemesi sunlari kontrol eder:

- Eksik malzeme kategorileri (orn. kolonlu ama kirissiz bina)
- Tutarsiz oranlar (orn. siva alaninin duvar alanindan cok buyuk olmasi)
- Insaat mantigi sorunlari (orn. beton kolonlu ahsap karkas)
- Eksik tipik kalemler (orn. bodrum icin su yalitimi olmamasi)

Yapay zeka incelemesi bulgulari her zaman **uyari** olarak raporlanir (asla hata degil), cunku yapay zeka degerlendirmeleri oznel olup yanlis olabilir. Bu uyarilari dikkatli inceleyin -- genellikle gercek sorunlari vurgularlar ancak kabul edilebilir sapmalari da isaretleyebilirler.

---

## Profesyonel Kullanim Icin Oneriler

1. **Ciktiyi her zaman nitelikli bir metrajciya inceletin.** Metraj bir tahmin aracidir, profesyonel muhakemenin yerini almaz.

2. **Denetim Izini kontrol edin.** Excel raporundaki ucuncu sayfa, fire payi ve kaynak eleman sayisi dahil olmak uzere her miktarin nasil turetildigini gosterir. Olagan disi gorunen herhangi bir kalemi dogrulamak icin bunu kullanin.

3. **Kritik kalemleri manuel olarak dogrulayin.** Yuksek degerli kalemler (beton, donati celigi) icin miktarlari BIM goruntleyicinizi kullanarak modelle karsilastirin.

4. **Fire paylarini kendi kosullariniza gore ayarlayin.** Varsayilan fire paylari sektor ortalamalarindan alinmistir. Santiye kosullarinizin farkli degerleri gerektirdigini biliyorsaniz, boru hattini calistirmadan once bunlari ayarlayin.

5. **Model tarafindan karsilanmayan kalemleri ekleyin.** MEP, gecici isler ve sahaya ozgu kalemler ayri olarak tahmin edilip keşif cetveline eklenmelidir.

6. **Metraji satin alma icin degil, butceleme icin kullanin.** Cikti, erken asamadaki maliyet planlamasi, fizibilite calismalari ve butce tahminleri icin en uygundur. Tedarik duzeyindeki miktarlar icin detayli insaat cizimleriyle dogrulayin.

---

## Dogruluk Uyarisi

Metraj, planlama ve butceleme amaclarina yonelik malzeme miktar tahminleri saglar. Bu tahminler, otomatik hesaplamalar ve yapay zeka destekli malzeme eslestirme kullanilarak IFC yapi modeli verilerinden olusturulur. Tahminler, profesyonel metrajciligin yerini tutmaz.

Kullanicilar su hususlarin farkinda olmalidir:

- Miktarlar, IFC modelinden oldugu gibi turetilir. Modeldeki hatalar veya eksiklikler tahminlere yansir.
- Fire paylari sektor ortalamalarindan alinmistir ve sahaya ozgu kosullari yansitmayabilir.
- Donati miktarlari, yapisal analizden degil standart oranlar kullanilarak tahmin edilir.
- Yapay zeka tarafindan olusturulan malzeme listeleri hata veya eksiklik icerebilir.
- Sistem yerel yapi yonetmelikleri, duzenlemeler veya saha kosullarini dikkate almaz.

Tum tahminler, satin alma, ihale veya insaat planlamasi icin kullanilmadan once nitelikli bir metrajci veya insaat profesyoneli tarafindan incelenmeli ve dogrulanmalidir.
