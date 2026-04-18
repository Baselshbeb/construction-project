# Glossary

A trilingual glossary of construction, BIM, and technical terms used in Metraj. Terms are provided in English, Turkish, and Arabic.

---

## Construction and BIM Terms

| English | Turkish | Arabic | Definition |
|---|---|---|---|
| Bill of Quantities (BOQ) | Metraj Listesi / Keşif Özeti | جدول الكميات | An itemized list of materials, parts, and labor needed for a construction project, with quantities and units for each item. |
| Metraj | Metraj | مترعج / حصر كميات | The Turkish term for quantity takeoff -- the process of measuring and listing all materials needed for construction from technical drawings or BIM models. |
| Quantity Takeoff | Metraj / Keşif | حصر الكميات | The process of extracting material quantities from building plans or models. Metraj automates this process. |
| IFC (Industry Foundation Classes) | IFC (Endüstri Temel Sınıfları) | IFC (فئات الصناعة الأساسية) | An open international standard (ISO 16739) for BIM data exchange. IFC files contain the 3D model, properties, and relationships of a building. |
| BIM (Building Information Modeling) | BIM (Yapı Bilgi Modellemesi) | BIM (نمذجة معلومات البناء) | A digital representation of a building's physical and functional characteristics, used for design, construction, and facility management. |
| IfcWall | IfcWall (Duvar) | IfcWall (جدار) | An IFC element type representing a wall -- a vertical building element that encloses or divides spaces. |
| IfcWallStandardCase | IfcWallStandardCase (Standart Duvar) | IfcWallStandardCase (جدار قياسي) | A simplified wall type with constant thickness and vertical extrusion. Common in IFC2x3 models. |
| IfcSlab | IfcSlab (Döşeme) | IfcSlab (بلاطة) | An IFC element type representing a horizontal structural element -- floor slabs, roof slabs, or ground slabs. |
| IfcColumn | IfcColumn (Kolon) | IfcColumn (عمود) | An IFC element type representing a vertical structural member that carries loads from beams and slabs to the foundation. |
| IfcBeam | IfcBeam (Kiriş) | IfcBeam (جسر / كمرة) | An IFC element type representing a horizontal or inclined structural member that transfers loads to columns. |
| IfcDoor | IfcDoor (Kapı) | IfcDoor (باب) | An IFC element type representing a door assembly including the leaf, frame, and hardware. |
| IfcWindow | IfcWindow (Pencere) | IfcWindow (نافذة) | An IFC element type representing a window assembly including the frame and glazing. |
| IfcStair | IfcStair (Merdiven) | IfcStair (سلم / درج) | An IFC element type representing a staircase, including flights and landings. |
| IfcRoof | IfcRoof (Çatı) | IfcRoof (سقف) | An IFC element type representing the roof structure and covering of a building. |
| IfcFooting | IfcFooting (Temel) | IfcFooting (قاعدة / أساس) | An IFC element type representing a foundation element that spreads building loads to the ground. |
| IfcCurtainWall | IfcCurtainWall (Giydirme Cephe) | IfcCurtainWall (جدار ستائري) | An IFC element type representing a non-load-bearing exterior wall, typically glass and metal framing. |
| Waste Factor | Fire Oranı / Kayıp Oranı | معامل الهدر / نسبة الفاقد | A percentage added to net material quantities to account for spillage, breakage, cutting waste, and over-ordering during construction. |
| Gross Area | Brüt Alan | المساحة الإجمالية | The total area of an element without any deductions for openings, recesses, or other features. |
| Net Area | Net Alan | المساحة الصافية | The area of an element after deducting openings (doors, windows) and other voids. |
| Storey | Kat | طابق / دور | A horizontal level or floor of a building (e.g., Ground Floor, First Floor). |
| Element Classification | Eleman Sınıflandırması | تصنيف العناصر | The process of assigning each building element to a BOQ category (substructure, frame, walls, etc.). |
| Material Mapping | Malzeme Eşleme | تخصيص المواد | The process of determining which construction materials are needed for a building element and in what quantities. |
| Formwork | Kalıp | قوالب صب / شدات | Temporary structures (usually wood or metal) used to contain and shape wet concrete until it hardens. Formwork quantities are measured in m2 of contact surface. |
| Reinforcement Steel | Donatı Çeliği | حديد تسليح | Steel bars (rebar) embedded in concrete to resist tensile forces. Measured in kg, with ratios of 50-200 kg per m3 of concrete depending on the element type. |
| Concrete Grade | Beton Sınıfı | رتبة الخرسانة | A classification of concrete by its compressive strength. Example: C25/30 means 25 MPa cylinder strength / 30 MPa cube strength. |
| Plaster | Sıva | لياسة / بياض | A coating applied to walls and ceilings for protection and finishing. Internal plaster and external plaster (cement render) have different compositions and waste factors. |
| Screed | Şap | ذراع تسوية | A thin layer of cement-sand mix applied on top of a structural slab to create a level floor surface, typically 50mm thick. |
| Waterproofing | Su Yalıtımı | عزل مائي | A membrane or coating applied to building elements (foundations, basements, wet areas) to prevent water penetration. |
| Insulation | Yalıtım / Isı Yalıtımı | عزل حراري | Material applied to external walls and roofs to reduce heat transfer, improving energy efficiency. |
| Soffit | Tavan Yüzeyi / Döşeme Altı | سقف سفلي | The underside of a slab or beam. Soffit area is used for ceiling plaster and formwork calculations. |
| Perimeter | Çevre | المحيط | The total outer edge length of an element. Used for skirting, coving, and slab edge formwork calculations. |
| Cross-Section Area | Kesit Alanı | مساحة المقطع | The area of a slice through a structural element (column, beam) perpendicular to its length. Used to calculate volume and surface area. |
| Substructure | Altyapı | البنية التحتية | Building elements below ground level: foundations, ground slabs, basement walls, piles. |
| Superstructure | Üstyapı | البنية الفوقية | Building elements above ground level: columns, beams, floor slabs, walls, roof. |
| Pset (Property Set) | Özellik Seti | مجموعة الخصائص | A named collection of properties attached to an IFC element (e.g., Pset_WallCommon contains IsExternal, FireRating). |
| Qto (Quantity Set) | Miktar Seti | مجموعة الكميات | A named collection of measured quantities attached to an IFC element (e.g., Qto_WallBaseQuantities contains Length, Height, GrossArea). |
| Audit Trail | Denetim İzi | مسار التدقيق | A record showing how each BOQ quantity was derived: base quantity, waste factor applied, source elements. Enables verification of the estimation. |

---

## Technical Terms

| English | Turkish | Arabic | Definition |
|---|---|---|---|
| Pipeline | İşlem Hattı | خط المعالجة | The sequence of processing stages that transforms an IFC file into a BOQ: Parse, Classify, Calculate, Map, Generate, Validate. |
| Agent | Ajan / İşlem Birimi | وكيل / عميل | A self-contained processing unit responsible for one stage of the pipeline. Each agent reads from and writes to the shared state. |
| Orchestrator | Orkestratör / Yönetici | المنسق | The master agent that runs all other agents in sequence and manages error handling and inter-stage validation. |
| WebSocket | WebSocket | WebSocket | A communication protocol that enables real-time bidirectional data exchange between the browser and server, used for live pipeline progress updates. |
| LLM (Large Language Model) | Büyük Dil Modeli | نموذج لغوي كبير | An AI model trained on large text datasets, capable of understanding and generating human language. Metraj uses Claude (by Anthropic). |
| Prompt Caching | İstem Önbellekleme | تخزين مؤقت للأوامر | An API feature that reduces cost by caching repeated system prompts, so subsequent calls with the same prompt are cheaper. |
