> Bu sayfa Turkce cevirisidir. [English version](../understanding-boq.md)

# Metrajin Anlasilmasi

Bu kilavuz, Metraj tarafindan olusturulan keşif cetvelinin (BOQ) nasil okunacagini ve kullanilacagini aciklar.

---

## Metraj Yapisi

Olusturulan metraj, standart insaat is kollarini takip eden bolumlere ayrilmistir. Her bolum ilgili malzemeleri gruplar ve her bolum icinde tekil kalemler, miktarlariyla birlikte belirli malzemeleri listeler.

### Bolum Sirasi

Bolumler asagidaki sirada goruntulenir (bos bolumler atlanir):

1. **Altyapi** -- Temeller, temel dosemeleri, bodrum malzemeleri
2. **Tasiyi Sistem (Kolon ve Kirisler)** -- Kolon ve kirisler icin beton, donati ve kalip
3. **Dis Duvarlar** -- Dis duvarlar icin yapisal malzemeler, dis kaplamalar ve su yalitimi
4. **Ic Duvarlar ve Bolmeler** -- Ic duvarlar icin tugla, blok veya beton ile ic kaplamalar
5. **Ust Kat Dosemeleri** -- Dosemeler icin beton, donati, kalip ve kaplamalar
6. **Cati** -- Cati yapisi ve ortme malzemeleri
7. **Kapilar** -- Kapi kanatlari, kasalari ve aksesuarlari
8. **Pencereler** -- Pencere birimleri ve denizlikleri
9. **Merdivenler ve Rampalar** -- Merdiven malzemeleri
10. **Kaplamalar** -- Zemin, duvar ve tavan kaplama malzemeleri
11. **MEP** -- Mekanik, elektrik ve tesisat (modellenmisse)
12. **Dis Cevre Isleri** -- Peyzaj ve saha malzemeleri (modellenmisse)

---

## Excel Rapor Yapisi

Excel raporu uc sayfadan olusur:

### Sayfa 1: Keşif Cetveli (BOQ)

Profesyonel bir duzene sahip ana metraj sayfasi:

**Baslik alani:**
- Baslik: "KEŞIF CETVELI" (veya seciminize gore Ingilizce/Arapca karsiligi)
- Proje adi (IFC dosyasindaki IfcProject varligindan)
- Bina adi (varsa)
- Tarih ve "Hazirlayan: Metraj AI System"

**Sutun basliklari:**

| Sutun | Baslik | Aciklama |
|---|---|---|
| A | Poz No. | Hiyerarsik kalem numarasi (orn. "2.03" = Bolum 2, Kalem 3) |
| B | Tanim | Malzeme adi ve ozellikleri |
| C | Birim | Olcu birimi (m2, m3, m, kg, ad, set) |
| D | Miktar | Fire payi dahil toplam miktar |
| E | Birim Fiyat | Birim fiyat -- kullanici tarafindan doldurulmak uzere bos birakilir |
| F | Tutar | Toplam maliyet -- formul: Miktar x Birim Fiyat |

**Bolum satirleri:** Her bolumun golgelendirilmis bir baslik satiri, ardindan kalemleri ve F sutunu icin TOPLAM formullu bir ara toplam satiri vardir.

**Genel toplam:** En altta, tum bolum ara toplamlarini toplayan bir genel toplam satiri bulunur.

**Ornek metraj kesiti:**

```
Poz No.  | Tanim                                 | Birim | Miktar
---------|---------------------------------------|-------|----------
         | 1. Altyapi                            |       |
1.01     | Beton C30/37                          | m3    |   45.200
1.02     | Donati celigi                         | kg    | 4,520.000
1.03     | Kalip (doseme)                        | m2    |  198.000
         | Ara Toplam - Altyapi                  |       |
         |                                       |       |
         | 2. Tasiyi Sistem (Kolon ve Kirisler)  |       |
2.01     | Beton C30/37                          | m3    |   32.400
2.02     | Donati celigi                         | kg    | 4,212.000
2.03     | Kalip (kolon)                         | m2    |  156.200
2.04     | Kalip (kiris)                         | m2    |   88.500
         | Ara Toplam - Tasiyi Sistem            |       |
         |                                       |       |
         | 3. Dis Duvarlar                       |       |
3.01     | Beton C25/30                          | m3    |   18.900
3.02     | Donati celigi                         | kg    | 1,512.000
3.03     | Kalip (duvar)                         | m2    |  252.000
3.04     | Dis siva (cimento esasli)             | m2    |  141.120
3.05     | Ic siva                               | m2    |  138.600
3.06     | Dis cephe boyasi                      | m2    |  138.600
3.07     | Ic cephe boyasi                       | m2    |  138.600
         | Ara Toplam - Dis Duvarlar             |       |
```

### Sayfa 2: Malzeme Ozeti

Tum bolumlerdeki malzemelerin duz bir listesi:

| Sutun | Baslik | Aciklama |
|---|---|---|
| A | No. | Sira numarasi |
| B | Malzeme | Malzeme tanimi |
| C | Birim | Olcu birimi |
| D | Toplam Miktar | Fire dahil toplam miktar |
| E | Kategori | Bu malzemenin hangi metraj bolumune ait oldugu |

Bu sayfa tedarik icin faydalidir -- tum siparis edilecek malzemelerin hizli bir gorunumunu saglar.

### Sayfa 3: Denetim Izi

Denetim izi, her metraj kalemi icin izlenebilirlik saglar:

| Sutun | Baslik | Aciklama |
|---|---|---|
| A | Poz No. | Sayfa 1 ile ayni kalem numarasi |
| B | Tanim | Malzeme tanimi |
| C | Birim | Olcu birimi |
| D | Net Miktar | Fire payi oncesi net miktar |
| E | Fire % | Uygulanan fire payi (orn. %5, %10) |
| F | Toplam Miktar (fire dahil) | Fire sonrasi nihai miktar: Net Miktar x (1 + Fire %) |
| G | Kaynak Elemanlar | Bu kaleme katkida bulunan IFC eleman sayisi |

Denetim izi, bir metrajcinin su islemleri yapmasini saglar:
- Her kaleme fire payinin nasil uygulandigini dogrulamak
- Net ve toplam miktarlar arasindaki farki anlamak
- Her bir kaleme kac yapi elemaninin birlestirildigini gormek
- Miktarlari kaynaklarina kadar izlemek

---

## Sayi Bicimlendirme

Miktarlar, okunabilirlik icin birim turune gore bicimlendirilir:

| Birim | Bicim | Ornek |
|---|---|---|
| m2 (metrekare) | 2 ondalik basamak | 138.60 |
| m3 (metrekup) | 3 ondalik basamak | 45.200 |
| m (metre) | 2 ondalik basamak | 25.50 |
| kg (kilogram) | 1 ondalik basamak | 4,520.0 |
| ad (adet) | Ondalik yok | 15 |
| set | Ondalik yok | 15 |

---

## Fire Payi Nasil Dahil Edilir

Metrajdaki her miktar zaten fire payini icerir. Sayfa 1'deki "Miktar" sutunu **toplam miktari** (net + fire) gosterir; bu, gercekte siparis edilmesi gereken miktardir.

Ayrinti gormek icin:
1. **Denetim Izi** sayfasini (Sayfa 3) acin
2. "Net Miktar" sutununu (net gereksinim) "Toplam Miktar" sutunuyla (fire dahil) karsilastirin
3. "Fire %" sutunu uygulanan orani gosterir

Ornegin, bir duvar 100 m2 ic siva gerektiriyorsa:
- Net Miktar: 100.00 m2
- Fire %: %10
- Toplam Miktar: 110.00 m2 (ana metrajda goruntulenen budur)

---

## Metraji Tedarik Icin Kullanma

### Adim 1: Malzeme Ozetini Inceleyin

Gereken tum malzemelere genel bir bakis icin Sayfa 2 (Malzeme Ozeti) ile baslayin. Bu size bir bakista alisveris listesi sunar.

### Adim 2: Birim Fiyatlari Ekleyin

Sayfa 1'de (Metraj) **Birim Fiyat** sutununu (E) tedarikcilerinizden aldiginiz guncel birim fiyatlarla doldurun. **Tutar** sutunu (F), `Miktar x Birim Fiyat` formuluyle otomatik olarak hesaplanacaktir.

### Adim 3: Bolum Ara Toplamlarini Inceleyin

Her bolumun bir ara toplam satiri vardir. Bunlar, o bolumdeki tum kalemlerin tutarlarini otomatik olarak toplar ve is kollarina gore maliyet dagilimi saglar.

### Adim 4: Genel Toplami Kontrol Edin

En alttaki genel toplam, tum bolum ara toplamlarini toplar ve tahmini toplam malzeme maliyetini verir.

### Adim 5: Denetim Izi ile Dogrulayin

Olagan disi gorunen herhangi bir kalem icin, su hususlari anlamak uzere Sayfa 3'u (Denetim Izi) kontrol edin:
- O miktara kac elemanin katkida bulundugu
- Hangi fire payinin uygulandigi
- Fire oncesi net miktarin ne oldugu

### Adim 6: Yerel Kosullara Gore Ayarlayin

Su durumlar icin miktarlari ayarlamayi dusunun:
- Varsayilanlardan farkli yerel fire oranlari
- IFC modeli tarafindan karsilanmayan malzemeler (MEP, saha isleri, gecici isler)
- Sartname degisiklikleri (farkli beton sinifi, farkli tugla turu)

---

## Dil Destegi

Metraj, yukleme sirasinda secilen dilde olusturulur:

| Dil | Bolum basliklari ornegi | Malzeme adlari |
|---|---|---|
| Ingilizce | "External Walls", "Structural Frame" | "Concrete C25/30", "Reinforcement steel" |
| Turkce | "Dis Duvarlar", "Tasiyi Sistem" | "Beton C25/30", "Donati Celigi B500" |
| Arapca | "الجدران الخارجية", "الهيكل الإنشائي" | "خرسانة C25/30", "حديد تسليح B500" |

Arapca raporlar, sagdan sola (RTL) sayfa yonlendirmesiyle olusturulur.

Metraji farkli bir dilde yeniden olusturmak icin dosyayi tekrar yuklemeden yeniden isleme ucnoktasini kullanin.

---

## CSV ve JSON Formatlari

### CSV

Bolum adi dahil, her metraj kalemi icin bir satir iceren duz bir dosya. Diger elektronik tablolara, veritabanlarina veya maliyet tahmin yazilimina aktarmak icin uygundur.

Sutunlar: Poz No., Tanim, Birim, Miktar, Net Miktar, Fire %, Birim Fiyat, Tutar, Bolum

### JSON

Tum bolumler, kalemler, proje meta verileri ve dogrulama sonuclari dahil olmak uzere tam metraj verilerinin yapilandirilmis bir gosterimi. Programatik erisim, diger sistemlerle entegrasyon veya ozel raporlama icin uygundur.
