> Bu sayfa Turkce cevirisidir. [English version](../uploading-ifc.md)

# IFC Dosyasi Yukleme

Bu kilavuz, yapi modelinden metraj (keşif) cikararak Bill of Quantities (BOQ) olusturmak isteyen insaat muhendisleri ve BIM koordinatorleri icin yazilmistir.

---

## IFC Dosyasi Nedir

IFC (Industry Foundation Classes), farkli yazilimlar arasinda yapi bilgisi paylasimi icin kullanilan acik bir uluslararasi standarttir (ISO 16739). Bir IFC dosyasi su bilgileri icerir:

- Her yapi elemaninin 3D geometrisi (duvarlar, dosemeler, kolonlar, kirisler, kapilar, pencereler vb.)
- Her elemanin ozellikleri (malzeme turu, yangin dayanimi, dis cephe olup olmadigi)
- Olculmus miktar bilgileri (uzunluk, yukseklik, alan, hacim)
- Mekansal yapi (her elemanin hangi kata ait oldugu)
- Malzeme katman bilgisi (cok katmanli duvarlarda: beton + yalitim + siva)

IFC dosyalari `.ifc` uzantisini kullanir ve STEP formatinda duz metin dosyalaridir. Basit bir konut icin birkac yuz kilobayttan, karmasik ticari bir yapi icin birkac yuz megabayta kadar degisebilir.

---

## Revit'ten IFC Disa Aktarimi

1. Yapi modelinizi Autodesk Revit'te acin
2. **File > Export > IFC** yolunu izleyin
3. IFC disa aktarim iletisim kutusunda:
   - **IFC Version:** IFC2x3 Coordination View 2.0 veya IFC4 Reference View secin
   - **File Type:** IFC (*.ifc)
   - **Property Sets** altinda:
     - **Export Revit property sets** secenegini isaretleyin
     - **Export IFC common property sets** secenegini isaretleyin (Pset_WallCommon vb. disa aktarir)
   - **Quantity Sets** altinda:
     - **Export base quantities** secenegini isaretleyin (Qto_WallBaseQuantities vb. disa aktarir)
   - **General** altinda:
     - **Export element materials** secenegini isaretleyin
4. Kayit konumunu secin ve **Export** dusesine tiklayin

**Onemli:** "Export base quantities" secenegi hayati onem tasir. Bu secenek olmadan Metraj, miktarlari temel boyutlardan turetmek zorunda kalir; bu da karmasik geometrilerde daha az dogruluk saglar.

---

## ArchiCAD'den IFC Disa Aktarimi

1. Yapi modelinizi Graphisoft ArchiCAD'de acin
2. **File > Save As** yolunu izleyin
3. Dosya turunu secin: **IFC Files (*.ifc)**
4. IFC Translator ayarlarini acmak icin **Options** tusuna basin:
   - Uygun bir translator secin (orn. "General Translator" veya "Coordination View 2.0")
   - **Data Conversion** altinda:
     - Ozellik setlerinin (Pset ve Qto) disa aktarildigindan emin olun
     - Malzeme disa aktarimini etkinlestirin
5. **Save** tusuna basin

ArchiCAD bazi miktarlar icin `NominalWidth`, `NominalHeight` ve `NominalLength` kullanir. Metraj'in miktar takma adi sistemi bunlari otomatik olarak isler.

---

## FreeCAD'den IFC Disa Aktarimi

1. Yapi modelinizi FreeCAD'de (BIM Workbench) acin
2. Model agacinda yapi veya arsa nesnesini secin
3. **File > Export** veya **Arch > IFC Export** yolunu izleyin
4. Disa aktarim iletisim kutusunda:
   - IFC2x3 veya IFC4 semasini secin
   - Secenek mevcutsa miktar disa aktarimini etkinlestirin
5. Dosyayi kaydedin

FreeCAD IFC disa aktarim kalitesi, surum ve modelin nasil olusturulduguna baglidir. BIM calisma tezgahi araclariyla (Arch Wall, Arch Slab vb.) olusturulan modeller en temiz sekilde disa aktarilir. En iyi sonuclar icin modelinizde genel sekiller yerine dogru BIM nesneleri kullandiginizdan emin olun.

---

## Dosya Gereksinimleri

| Gereksinim | Ayrintilar |
|---|---|
| Dosya uzantisi | `.ifc` (buyuk/kucuk harf duyarsiz) |
| Dosya formati | Gecerli IFC/STEP formati (`ISO-10303-21` ile baslamali) |
| Maksimum dosya boyutu | 500 MB |
| IFC semasi | IFC2x3 veya IFC4 |
| Onerilen disa aktarimlar | Miktar setleri (Qto), ozellik setleri (Pset), malzemeler |

---

## Daha Iyi Sonuclar Icin Ipuclari

### Miktar Setlerini Ekleyin

Dogru metraj icin en onemli faktor, IFC dosyanizda miktar setlerinin (Qto) bulunmasidir. Bunlar, BIM aracinizin 3D geometriden hesapladigi GrossArea, NetArea, GrossVolume gibi onceden hesaplanmis miktarlardir. Bunlar olmadan Metraj, miktarlari temel boyutlardan turetir ki bu yaklasik bir degerdir.

### IsExternal Ozelligini Ayarlayin

Duvarlarda `IsExternal` ozelligi, duvarin dis duvar (dis siva, boya ve muhtemelen yalitim ile) mi yoksa ic duvar (her iki yuzeyde siva ve boya ile) mi olarak isleneceini belirler. Bu ozellik ayarlanmamissa, yapay zeka siniflandiricisi duvar adina ve konumuna gore en iyi tahminini yapar.

### Malzeme Atayin

BIM modelinizde elemanlara malzeme atanmissa (orn. "Beton C25/30", "Tugla"), bu bilgi yapay zeka malzeme eslestricisine baglam olarak iletilir ve daha dogru malzeme secimleri saglar.

### Standart Eleman Turlerini Kullanin

Genel geometri (Extrusion, Mesh) yerine dogru BIM eleman turleri (Wall, Slab, Column, Beam) kullanin. Metraj, 18 farkli IFC eleman turunu tanir. `IfcBuildingElementProxy` olarak disa aktarilan genel geometri yine de islenir, ancak daha az ozgullukle.

### Kata Gore Duzenleyin

Elemanlari dogru yapi katlarina atayin. Metraj kat bilgisini su amaclarla kullanir:
- Her kat icin gercek aciklik oranlarini hesaplamak (kapi + pencere alaninin duvar alanina yuzdesi)
- Altyapi siniflandirmasi icin temel seviyesindeki elemanlari belirlemek
- Dogrulama sirasinda her katta eksik elemanlari tespit etmek

---

## Yukleme Sonrasi Ne Olur

Bir IFC dosyasi yuklediginizde, asagidaki boru hatti asamalari otomatik olarak calisir:

### Asama 1: IFC Ayristirma (5-30 saniye)

Sistem, IfcOpenShell kullanarak IFC dosyanizi okur ve her yapi elemanini cikarir. Her eleman icin eleman turu, adi, kati, miktarlari, ozellikleri ve malzemeleri okunur. Ilerleme guncellemesinde eleman sayisini goreceksiniz.

### Asama 2: Siniflandirma (3-10 saniye)

Claude AI her elemani inceler ve onu bir metraj bolumune (altyapi, tasiyi sistem, dis duvarlar, ic duvarlar vb.) atar. Bu, nihai metrajinizin organizasyonunu belirler.

### Asama 3: Miktar Hesaplama (1-3 saniye)

Sistem, ham IFC verilerinden insaatla ilgili miktarlari hesaplar. Duvarlar icin brut alan, net alan (gercek aciklik dusulmusleri ile), hacim ve kaplama icin yuzey alanlari hesaplanir. Dosemeler icin alan, hacim, cevre ve kalip alani hesaplanir.

### Asama 4: Malzeme Eslestirme (5-15 saniye)

Claude AI, sanal bir metrajci olarak her eleman icin gereken tum insaat malzemelerini belirler. Buna yapisal malzemeler (beton, celik, kalip), kaplamalar (siva, boya, fayans) ve koruyucu malzemeler (su yalitimi, isi yalitimi) dahildir. Sektore uygun fire paylari uygulanir.

### Asama 5: Metraj Olusturma (1-2 saniye)

Malzemeler, numaralandirilmis bolumler ve kalemler halinde yapilandirilmis bir keşif cetveline duzenlenir. Bolum basliklari sectiginiz dilde olusturulur.

### Asama 6: Dogrulama (3-8 saniye)

Sekiz aritmetik kontrol ciktiyi dogrular (negatif miktar yok, makul beton oranlari vb.), ardindan eksik malzemeler, olagan disi miktarlar veya insaat mantigi sorunlarini arayan bir yapay zeka muhendislik incelemesi yapilir.

### Disa Aktarim (1-3 saniye)

Metraj, Excel (.xlsx), CSV ve JSON dosyalari olarak disa aktarilir. Excel dosyasi uc sayfa icerir: ana metraj, malzeme ozeti ve denetim izi.

### Ilerleme Cubugu

Web arayuzu, her asamadan sonra guncellenen bir ilerleme cubugu gosterir. Gosterilen ilerleme yuzdeleri:
- IFC Ayristirma: %17
- Siniflandirma: %33
- Miktar Hesaplama: %50
- Malzeme Eslestirme: %67
- Metraj Olusturma: %83
- Dogrulama/Disa Aktarim: %95-100

Tipik bir konut yapisi (50-200 eleman) icin toplam isleme suresi 30-90 saniyedir. Daha buyuk ticari yapilar 2-5 dakika surebilir.
