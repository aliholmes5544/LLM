# PROJECT STATE — "LLM vs. LLM" Master's Thesis
**Checkpoint date:** 2026-10-06 · **Status:** Chapters 1–2 content-complete · Chapter 3 starting (§3.1 drafted, awaiting review)

> كيف تستخدم هذا الملفّ: افتح محادثة جديدة، ارفع هذا الملفّ + `capter1.docx` + `capter_2.docx` + ملفّ المراجع، واكتب: "استأنف من PROJECT_STATE.md، نبدأ §3.2". كل ما أحتاجه موجود هنا.

---

## 1. القواعد الثابتة (Standing Rules)

- **الدور:** مستشار أكاديميّ أوّل (أمن سيبرانيّ + ذكاء اصطناعيّ فقط).
- **اللغة:** نصّ الرسالة = إنجليزيّة أكاديميّة (American English). النقاش = عربيّة.
- **الأسلوب:** لا em dashes. APA 7. كل ادّعاء واقعيّ مُستشهَد له أو يُحذف. لا مبالغة؛ التمييز بين ما يقوله المصدر حرفيًّا وتحليلي ("as an analytical observation"). أقسام الفصل ٢ ~650–735 كلمة (قُبل تجاوزها عند الحاجة).
- **القاعدة الفوقيّة:** بعد أيّ تعديل أكتب النسخة النهائيّة الكاملة للقسم.
- **سير التحقّق:** المستخدم يرسل "ملاحظات سلبيّة" لكل قسم؛ أتحقّق من **كل** ملاحظة من المصدر الأصليّ (بحث/تنزيل) ثم أؤكّد أو أصحّح. لا استشهاد بلا بيانات ببليوغرافيّة مؤكّدة.
- لا أعدّل ملفّات المستخدم مباشرةً؛ هو يطبّق يدويًّا (إلّا إن طُلب إنتاج ملفّ مصحّح برمجيًّا).
- المستخدم على Windows RTL. ملفّات الفصول المرجعيّة: `capter1.docx`، `capter_2.docx` (النسخ المحدّثة بعد جلسة Paladin). قائمة المراجع في **ملفّ منفصل** عند المستخدم.
- زمن الفصل ٣: **المضارع** (التجارب لم تُجرَ)؛ يُحوَّل للماضي لاحقًا إن اشترط القسم.

---

## 2. هويّة الرسالة

**Title:** *LLM vs. LLM: Evaluating the Effectiveness of Open-Source Language Models in Detecting AI-Generated Spear-Phishing Emails*

**RQ1** Effectiveness (accuracy, precision, recall, F1, FPR) · **RQ2** Comparison across open models + ML/DL baselines · **RQ3** Zero-shot vs prompt-engineered · **RQ4** Robustness under paraphrased/obfuscated inputs.

**O1** benchmark dataset (public corpora + *published* AI-generated spear-phishing + derived paraphrased/obfuscated variants) · **O2** model selection · **O3** pipeline supporting prompting strategies · **O4** evaluation vs baselines · **O5** degradation measurement + error analysis · **O6** practical conclusions.

**Four contributions:** (1) comparative evaluation of open LLMs as *direct* detectors; (2) characterization of prompting strategy; (3) robustness analysis; (4) reproducible framework (dataset + pipeline → GitHub repo).

**The gap (three properties never combined):** open-source model run locally + direct prompt-based detection + target = AI-generated spear-phishing email. Koide (direct, proprietary, general) · Nasution (open, direct, URLs) · Nahmias (AI-gen spear, hybrid) · Pajola (direct, proprietary, LLM-gen phishing mixed) · Pang/Paladin (generation-side, not a detector) · **This study ✓✓✓**.

---

## 3. الورقة المحوريّة — القرار النهائيّ (مُتحقَّق منه)

- **Core paper = Pang et al. (2026), Paladin, NDSS 2026.** مؤكّدة: PDF على موقع NDSS، DOI `10.14722/ndss.2026.232522`، ISBN 979-8-9919276-8-0، Session 2D، شارات Artifact (Available/Functional/Reproduced)، كود على Zenodo (MIT).
- **Chen et al. (2026) = الإطار المفاهيميّ فقط، مسودّة arXiv** (ليست في NDSS 2026 — تحقّقت من قائمة المقبولات وLAST-X؛ v1 كانت لـ USENIX). تُستشهد كـ preprint، عنوان v3 القصير، DOI `10.48550/arXiv.2508.21457`.
- **التموضع:** Paladin تدافع من جهة التوليد وتفترض نموذجًا مُجهَّزًا؛ رسالتي من جهة الكشف، **generator-agnostic** (لا تتطلّب معرفة أو تعاون المولِّد؛ الأداء قد يعتمد على الكاشف — RQ2). Paladin تقول إن الكشف بالـ LLM مكلف ومقيّد بالنموذج؛ رسالتي **تفحص model-dependence** (RQ2) **ولا تقيّم الكلفة** (تشغيل محليّ بدل خدمة مقنّنة فقط).
- ⚠️ لا أستخدم "model-agnostic" أبدًا؛ المصطلح الصحيح **generator-agnostic** كإعداد/تصميم، بلا إيحاء باستقلال الأداء عن المولِّد.

---

## 4. حالة الفصل ١ (مكتمل، معتمد — أُعيد بناؤه على قالب الدكتور، 2026-10-18)

**الهيكل النهائيّ (قالب القسم):** 1.1 Background and Context · 1.2 Problem Statement · **1.2.1 Threat Model** · 1.3 Motivation · 1.4 Research Objectives · 1.5 Research Questions · 1.6 Scope and Limitations · 1.7 Contributions · 1.8 Thesis Organization.

**الملفّ المعتمد:** `Chapter1_v3_template.docx` (في outputs). الفحص الآليّ: الفقرات الـ 66 الأصليّة كلّها حاضرة، لا إحالة يتيمة، التعديلات المؤجَّلة #1–#4 مطبَّقة، Kim 2025b مصحَّح، التكرار مخفَّض (GPT-family 5→3 مرّات)، تقييد «hosted API/services» للنماذج التجاريّة، جملة «study evaluates only the first condition» في نموذج التهديد.

**خريطة الترقيم القديم → الجديد:** 1.1+1.2→1.1 · 1.3→**1.2.1** · 1.4+1.5→1.3 · 1.6→1.2 · 1.7→1.4+1.5 · 1.8→1.7 · 1.9→**1.6** · (جديد) 1.8.

**Threat Model (§1.2.1) — المحتوى المعتمد:** goal (deliver + evade; **study evaluates only the detection condition**) · capabilities (LLM access without jailbreak [Saha Roy 2024]; automated reconnaissance [Hazell 2023; Czybik 2026; Kim 2025b]; refinement e.g. paraphrasing [Chen 2026]; obfuscation = study-defined controlled transformation) · knowledge = **black-box, non-adaptive** (plausible setting; consistent with Chen; matches design) · defender = open model, local, text only (subject+body), no fine-tuning · assumptions: generator not cooperative (generator-agnostic, vs Paladin), attacker non-adaptive · out of scope: adaptive/partial-knowledge attacker; prompt-injection against the detector.

**1.8 Thesis Organization:** مكتوب لخمسة فصول (Intro / Lit Review / Methodology / Results & Discussion / Conclusion) — يُعدَّل إن اختلف قالب الدكتور.

**مؤجَّل للتنسيق فقط:** أنماط العناوين (H1/H2/H3) وتوحيد المتن على Normal؛ قائمة المراجع الـ19 الملحقة بالملفّ تُزال عند التجميع.

---

## 5. حالة الفصل ٢ (مكتمل، معتمد)

Overview (unnumbered) · 2.1–2.9 · Figure 2.1 (open vs proprietary) · Figure 2.2 (confusion matrix) · Table 2.1 (Study / Model(s) / LLM as direct detector / Target: AI-gen spear-phishing / Task–result): Heiding 2024 · Koide 2025 · Nasution 2025 · Nahmias 2024 · **Pang 2026 (✗ tag at generation, ✗ general)** · This study.

**§2.4 final** يتضمّن فقرة Paladin ("The approach therefore integrates the detection signal into the generation process itself, in contrast to post-hoc detection methods." + analytical observation عن الافتراض) وخاتمة تُحيل التموضع إلى §2.8. Koide: "superior to the several LLMs and baseline systems against which it was compared". Nahmias: بلا جملة "ongoing maintenance".
**§2.8 final** يتضمّن فقرة تموضع Paladin + "by training a dedicated classifier" + "cost is not evaluated as such" + Kim (2025a).

---

## 6. قائمة المراجع (ملفّ منفصل عند المستخدم)

31 مرجعًا مؤكّدًا + **Pang 2026** (مضاف) + **Pajola 2025** (مؤجَّل) = **33**. Chen بصيغة preprint. Kim مميّزة a/b (Kim, H. 2025b = USENIX agents؛ Kim, S. H. 2025a = Eurorad).

**Pang:** Pang, Y., Meng, W., Liao, X., & Wang, T. (2026). Paladin: Defending LLM-enabled phishing emails with a new trigger-tag paradigm. In *Proceedings of the 2026 Network and Distributed System Security Symposium (NDSS 2026)*. Internet Society. https://doi.org/10.14722/ndss.2026.232522

**Chen:** Chen, F., Wu, T., Nguyen, V., & Rudolph, C. (2026). *SoK: Exposing the generation and detection gaps in LLM-generated phishing* (arXiv:2508.21457v3) [Preprint]. arXiv. https://doi.org/10.48550/arXiv.2508.21457

**Pajola:** Pajola, L., Caripoti, E., Banzer, S., Pizzi, S., Conti, M., & Apruzzese, G. (2025). E-PhishGEN: Unlocking novel research in phishing email detection. In *Proceedings of the 18th ACM Workshop on Artificial Intelligence and Security (AISec '25)* (pp. 64–76). Association for Computing Machinery. https://doi.org/10.1145/3733799.3762967

---

## 7. التعديلات المؤجَّلة — **لا شيء متبقٍّ** (العشرة كلّها طُبّقت: #1–#4 في إعادة بناء الفصل ١، #5–#9 في إعادة بناء الفصل ٢، #10 التنسيق يتولّاه LaTeX)

**الفصل ٢ — الحالة النهائيّة (2026-10-21):** Word مكتمل بهيكل الدكتور (13 عنوانًا)، وLaTeX مكتمل ومدفوع (آخر commit `f3a3438`). 28 مفتاح استشهاد، شكلان (`fig:open-vs-proprietary` في 2.3.3، `fig:confusion-matrix` في 2.3.5، كلاهما PNG مائيّ مولَّد)، Table 2.1 (`tab:lit-compare`، 7 صفوف، الملاحظة داخل العوّامة، ✓/✗ بخطّ DejaVu). labels الأقسام الفرعيّة: `sec:lit-phishing`, `sec:lit-detection`, `sec:lit-offensive`, `sec:lit-defensive`, `sec:lit-open`, `sec:lit-prompting`, `sec:lit-eval`.

**تعديلات المحتوى المقبولة من جولتَي الملاحظات (مطبَّقة في Word وLaTeX):** فقرة نطاق المراجعة في 2.1 (narrative; Crossref/arXiv check) · «a spear-phishing attack combines reconnaissance» · قيد أمانة التفسير في 2.3.2 · Nasution «the best of the larger ones… reached or exceeded 90%» (الملخّص يناقض الجداول) · اعتماد Precision/F1 على نسبة الفئة في 2.3.5 · إحالة الفصل 3 في 2.3.4 · عنوان عمود «open = locally deployable» + ملاحظة «not whether the cited study ran the model locally» · «labeled training data… nor the labeled data still needed for evaluation and for few-shot examples» في 2.5.

**المراجع — الحالة:** 33 مدخلًا في `reference.bib`، فُحصت ضدّ Crossref/arXiv (`reports/reference_check.md`). تصحيحات: عنوان Saha Roy المنشور، Kytidou 19(6) 4356–4379، Kim 2025a رقم العدد 1، Goldenits eid، FBI `shortauthor`. **فحوص ما قبل التسليم (تعليقات داخل الملفّ):** Chen v4 أعاد التسمية — تُقرأ ويُقرَّر؛ Koide بقي 2025 (نسخة SecureComm)؛ Czybik بلا DOI — يُتحقّق من صفحة USENIX.

ملاحظة: نسبة 61٪/32٪ (موجّه/عامّ في E-PhishLLM) **قياسي أنا** — تُذكر في الفصل ٣ فقط، لا في الفصل ٢.

---

## 8. قرارات التصميم المقفلة للفصل ٣

| القرار | المعتمد |
|---|---|
| البيانات | **جاهزة، لا توليد** |
| التصيّد الموجّه المولّد (النواة) | **Nahmias et al. (2024)**: 334 spear_phishing |
| اختبار التعميم (منفصل، لا يُدمج) | **E-PhishLLM** (Pajola 2025): الإنجليزيّة فقط، مع علامة "personalized" |
| السليم | Enron ham (3,000) + SpamAssassin hard ham (490) من مستودع Nahmias + E-PhishLLM EN legit (5,506، حديث) |
| التقليديّ | Nahmias traditional_phishing (3,332) — تدريب خطوط الأساس + مقارنة RQ2 (بروتوكول Nahmias: train on traditional+ham, test on spear) |
| RQ4 | **اشتقاق آليّ** من رسائل Nahmias: **paraphrasing + obfuscation** بمستويات شدّة + فحص حفظ المعنى (تضمين + عتبة + مراجعة يدويّة) |
| المولِّد ≠ الكاشف | محلول تلقائيًّا: مولِّد Nahmias مملوك، الكواشف مفتوحة |
| تسريب few-shot | الأمثلة **ليست** من شخصيّات Nahmias (SafeSecurity وشخصيّاتها المتكرّرة) |
| مسار الحوسبة | **B — هجين**: جهاز المستخدم للنماذج ≤8B، Colab للكبيرة (14B–32B، وربّما 70B بتكميم أدنى) |
| الباك-إند | **llama.cpp / GGUF (Q4_K_M)** موحّد على الجهاز والسحابة (لا متغيّر مخفيّ) |
| السحابة | **Colab Pay-As-You-Go** (100 وحدة ≈ 10$) — **ليس** GCP VM؛ لا شراء قبل أن يعمل الكود محليًّا |
| التطوير | Claude Code على الجهاز → GitHub → Colab يسحب ويشغّل؛ نتائج CSV صغيرة تعود للمستودع/Drive؛ السحابة مؤقّتة |
| المستودع | `llm-vs-llm/` : README, requirements.txt, configs/ (local.yaml, cloud_large.yaml), scripts/01_download_data.py … 06_evaluate.py, prompts/, results/, notebooks/cloud_run.ipynb, .gitignore (data/ models/ .env), .env.example. لا بيانات ولا أوزان ولا أسرار في المستودع. وسوم إصدار. |
| الكود ↔ الفصل | كل قسم منهجيّة يُعتمد → يُنفَّذ سكربته فورًا (3.2→01–03، 3.4→04، 3.5→05، 3.7→06) |

**قرارات ما زالت مفتوحة:** نموذج مملوك كنقطة مرجعيّة (نعم/لا؛ يحتاج API) · هل تشترط الجامعة IRB · قالب القسم لفصل المنهجيّة · حجم عيّنة السليم/التوازن وعدد البذور (أقترح) · أداة إعادة الصياغة وقواعد التمويه (أقترح) · الاختبارات الإحصائيّة (أقترح McNemar + bootstrap CIs).

---

## 9. حقائق البيانات المؤكّدة (بالتنزيل والفحص)

**Nahmias** (`github.com/nahmiasd/Prompted-Contextual-Vectors-for-Spear-Phishing-Detection`, CC BY-NC-SA 4.0): `data/emails/{spear_phishing 334, traditional_phishing 3332, enron_ham 3000, hard_ham 490}`; JSON fields: email_subject, sender_name, email_body (**HTML** → يحتاج تنظيفًا). قيد: كل الـ 334 في شركة خياليّة واحدة (SafeSecurity) بشخصيّات متكرّرة وموضوعات أمن/مؤتمرات → تسريب محتمل في few-shot، تجانس يُوثَّق كقيد.

**E-PhishLLM** (`github.com/pajola/e-phishGen`, ملفّ `ephishLLM.json`, **لا ملفّ ترخيص** → لا إعادة توزيع، سكربت تنزيل): 16,616 رسالة؛ fields: Subject, Body, type (0 legit/1 phish), Language; **EN: 11,502 = 5,996 phish + 5,506 legit**; body median ~81 كلمة؛ الروابط `<<link>>`. قياسي: تحيّة باسم 61٪ / عامّة 32٪ / بلا تحيّة 7٪ → **مختلطة، ليست spear خالصة**.

---


## 9b. الخطوة 05 — النتائج النهائيّة على مجموعة التطوير (2026-10-25، مجمَّدة)

- **العتبات المجمَّدة:** `thr_cos = 0.68` (أعلى قيمة يجتازها ≥95% من المحفوظات بشريًّا: 97.1%)؛ `thr_nli = 0.70` مثبَّتة مسبقًا — **غير قابلة للمعايرة** لأن fallback الجمليّ يُعيد كلّ جملة <0.70 قبل القياس (censored). الباقي كما في `configs/variants.yaml`.
- **التقييم البشريّ:** ثلاثة مقيّمين A/B/C، 60 صفًّا (57 + 3 صياغات تغيّر نصّها)، تسمية الأغلبيّة، لا صفّ منقسم. اتّفاق المعنى 86.7/95.0/91.7%، PABAK 0.73/0.90/0.83، Fleiss 0.16 (مفارقة الانتشار: 55/60 محفوظ — يُبلَّغ بالثلاثة). B: ثلاثة «not» خطأ تطبيق («link missing» في رسائل بلا رابط) — **يبقى**، الأغلبيّة تتكفّل.
- **cosine لا يميّز المعنى:** الاستبعادات بـ cosine وحده (0.625، 0.686، 0.731، 0.752، 0.794): أربعة محفوظة بالإجماع، والـ«جزئيّ» (0.731) في وسطها. خفض العتبة من 0.80 إلى 0.68 أعاد 4 من 5. eph:14228#para_high (0.625) يبقى مستبعدًا — حالة سليمة رفضتها العتبة، تُذكر.
- **خفض العتبة غيّر نصّ 8 صياغات** (المحاولة الأولى صارت مقبولة) → أُعيد تقييمها على النصّ المقبول. eph:12308#para_high «جزئيّ» في النسختين — المُعيد صياغتها يُفسد هذه الرسالة بثبات.
- **الخطأ المتبقّي (مقبولات، عتبات مجمَّدة):** صياغة 2/36 = 5.6% [Wilson 1.5–18.1%] (12308#para_high، 14356#para_high: invoice→bill of lading)؛ تشويش 0/20؛ الكلّ 2/56 = 3.6% [1.0–12.1%]؛ «not» = 0. لا شرط يُراجَع كاملًا (قاعدة 5%).
- **المقروئيّة (20 تشويش):** أغلبيّة 1 في 20/20؛ صفر = 0/10 في كلّ شرط؛ 2 مرّة واحدة. ⇒ الشدّتان مقروءتان؛ **التشويش ملحوظ لقارئ متأنٍّ** — خاصّيّة الشرط تُذكر في وصفه.
- **عدّ التطوير (cos 0.68):** para_low 81/19/0، para_high 76/20/4 (1 cosine + 3 fraction)، obf 100/100 سلامة.
- **حوادث تُذكر في الفصل 4:** (1) `auto_outcome`/`failed_tests` كانا ظاهرين للمقيّمين؛ (2) ترميز cp1256 شوّه العرض في 29 صفًّا — أُعيد تقييم التشويش على نصّ نظيف ولم تتغيّر تسمية واحدة.
- **الملفّات:** `reports/manual_review_sample_dev.csv` (60 صفًّا، أعمدة `_prov`/`_cp1256` للسجلّ)، `reports/readability_dev.xlsx`، `reports/variants_calibration_provisional.json`، `reports/ratings_merge_dev.json`، `scripts/05a_merge_ratings.py`، `docs/CHANGES_FOR_THESIS.md`.
- **التالي:** تشغيل 05 **مرّة واحدة** على core_pos وctrl_para_legit بالإعدادات المجمَّدة (لا مراجعة يدويّة على بيانات التقييم) → ثم الخطوة 06 (النماذج/التوجيه/الاستدلال).

---


## 9c. الخطوة 05 على مجموعة الاختبار — منتهية (2026-10-27) · الخطوة 06 — مواصفة معتمدة

- **اشتقاق التقييم (تشغيل واحد، إعدادات مجمَّدة، commit a8dbb6f→3d3a10b):** core_pos 334 × {para_low, para_high, obf_low, obf_high} + ctrl_para_legit 334 × {para_high} (المنهجيّة §3.2.3: لا تشويش على الشرعيّ). 8 h 18 min على CPU (3.1–3.5 s/توليد؛ 7,064 توليد أوّل + 1,164 إعادة). **التطابق:** تشغيلان متطابقان بايتًا من الذاكرة. **الفحص العيّنيّ بلا ذاكرة:** 171/179 جملة متطابقة، 8 اختلفت بكلمة–3 ⇒ التوليد seeded لكنه **غير متطابق بايتًا على CPU** (خاصّيّة llama.cpp). **القرار:** `variants_eval.jsonl` + `paraphrase_cache_eval.jsonl` هما القطعة الثابتة (بصمتاهما في `reports/variants_eval_fixed_artifacts.json`)؛ تُؤرشفان عند التسليم تحت CC BY-NC-SA 4.0، لا في git. صياغة §3.8 (الآن 4.2.1/3.7) تقول ذلك.
- **العدّ:** core_pos para_low 334/0، para_high 325/9 (fraction)، obf 334/334 سلامة 100%؛ ctrl_para_legit 213 مقبول / 121 مستبعد (36.2%). **تشخيص (Q7):** رسائل Enron قصيرة (وسيط 95 كلمة، 5 جمل مؤهَّلة) حيث لا تسمح عتبة 0.80 بإعادة جملة واحدة؛ enron_ham 44% مستبعد مقابل hard_ham 20%. خاصّيّة البيانات لا المنهج؛ **لا تغيير في العتبات**. تصحيح منطقيّ لاحق: المتغيّر المطابق للأصل حرفيًّا يُستبعد («unchanged») ⇒ الضوابط المتوقّعة 210. **Table 3.2:** ≈3,210 عنصرًا لكلّ كاشف لكلّ استراتيجيّة (يُقرأ العدد النهائيّ من `CHANGES_FOR_THESIS.md`).
- **الخطوة 06 — القرارات الأربعة مقفلة (2026-10-27)، المواصفة في `docs/TASK_06_detection.md`:**
  1. **النماذج (6، GGUF Q4_K_M، llama.cpp):** Llama-3.1-8B-Instruct، Mistral-7B-Instruct-v0.3، gemma-2-9b-it، Qwen2.5-7B-Instruct (جهاز) · Qwen2.5-14B-Instruct (Colab T4) · gemma-2-27b-it (Colab L4). عمود ترخيص لكلّ نموذج. **مُعيد الصياغة في 05 يُستبعد من الكواشف** (يُقرأ من `configs/variants.yaml`؛ المرجّح Phi-3.5).
  2. **التوجيه (4):** zero_shot (مرجع) · few_shot (4 أمثلة ثابتة 2+2 من `fewshot_pool`، فحص الشخصيّات) · cot (`FINAL: X`) · role. فكّ ترميز حتميّ (T=0، seed)، تشغيل واحد. تطوير الموجِّهات على `dev` فقط ولإصلاح الامتثال للصيغة لا الدقّة؛ تجميد ببصمة.
  3. **الخطوط المرجعيّة:** tfidf_lr، tfidf_svm (بروتوكول Nahmias)، DistilBERT مضبوط (T4)، + **مرجع مملوك zero-shot فقط** (≈2–4$، يُتخطّى بلا مفتاح؛ النطاق يسمح: «points of comparison»).
  4. **الاستخراج:** تطبيع → (cot: بعد آخر `final:`) → رمز واحد فقط = التصنيف؛ كلاهما/لا شيء/فارغ = `invalid` → يُحتسب خطأً + نسبة + تحليل حساسيّة؛ لا إعادة محاولة.
  - **بوّابة الدخان:** invalid ≤10% لكلّ خليّة على dev قبل أيّ تشغيل تقييم. **الخطر الأكبر: الزمن** (~77k استدلال) — يُقاس في خطوة 3 من ترتيب العمل قبل الالتزام؛ قد يُنقل مزيد إلى Colab.
- **تحسينات إن بقي وقت (بالترتيب):** معيار اختيار النماذج مكتوبًا في 3.5 → تحليل أخطاء نوعيّ (30 رسالة) → حساسيّة صياغة الموجِّه على dev → few-shot بـ 8 → 70B على A100 → واجهة Gradio للمناقشة.
- **الفصل 3 — ما يُكتب من الملفّات ومتى:** 3.1 جديد · 3.2 ← §3.1 القديمة + Table 3.1 · 3.4 ← Figure 3.1 (تُعاد مائيّة) · 3.5/3.6/3.7 ← TASK_05 + TASK_06 + configs + الكود **بعد** بناء 06 (يُكتب عن كود يعمل) · 3.3 Requirements جديد (من CLAUDE.md والقواعد) · 3.8 جديد. ملفّات مطلوبة من `~/llm`: README، CLAUDE.md، docs/METHODOLOGY_3.2.md، docs/TASK_05_variants.md، docs/TASK_06_detection.md، docs/CHANGES_FOR_THESIS.md، configs/*.yaml، prompts/*، requirements.txt، شجرة scripts/.
- **GitHub:** مفتاح SSH جديد `llm-thesis-wsl` بلا كلمة مرور؛ الدفع يعمل من WSL. Windows Update يجب إيقافه مؤقّتًا أثناء التشغيلات الطويلة (أعاد التشغيل ليلة 26–27/10 دون ضرر).
- **التالي:** أمر الخطوة 06 بند 1 (إعدادات، موجِّهات، استخراج، اختبارات) → مراجعة الموجِّهات وأمثلة few-shot → دخان على dev → قياس الزمن → تقييم.

---

## 10. خطّة الفصل ٣ (Methodology)

| § | القسم | الحالة |
|---|---|---|
| 3.1 | Research Design Overview + Table 3.1 | **مسودّة جاهزة (أدناه)، بانتظار الملاحظات السلبيّة** |
| 3.2 | Dataset Construction: 3.2.1 sources & rationale · 3.2.2 preprocessing · 3.2.3 variant derivation (operational definitions, intensity, meaning check) · 3.2.4 composition & splits (table) | **التالي** |
| 3.3 | Model Selection (criteria: open-source vs open-weight per §2.5, size, license; ≤8B on laptop, larger on Colab; GGUF Q4_K_M) | بعد pilot |
| 3.4 | Prompting Strategies (zero-shot reference; few-shot/CoT/role; full prompts in appendix; output parsing) | مستقلّ عن العتاد |
| 3.5 | Baselines (TF-IDF + LR/SVM; optional fine-tuned BERT; optional proprietary reference) | بعد قرار المملوك |
| 3.6 | Experimental Procedure (decoding settings, label extraction rule, invalid outputs, runs/seeds, pilot mention) | بعد pilot |
| 3.7 | Evaluation Metrics (tied to Figure 2.2; degradation Δ; McNemar/bootstrap) | مستقلّ |
| 3.8 | Environment & Reproducibility (laptop specs + Colab GPU; same backend/quantization; weights loaded directly, no API; versions, hashes, seeds; GitHub tag) | بعد pilot |
| 3.9 | Ethical Considerations (published data, licenses, no generation, no dissemination, IRB if required) | مستقلّ |
| 3.10 | Chapter Summary | أخيرًا |

Figure 3.1 (pipeline, 6 stages + baseline branch) تُرسم بعد اعتماد §3.1. استراتيجيّة البحث في الأدبيّات → ملحق. مراجع بيانات تُضاف في الفصل ٣: Enron (Klimt & Yang, 2004), SpamAssassin corpus.

---

## 11. البنية التحتيّة (الحالة الفعليّة)

- **جهاز المستخدم:** Windows، Ryzen مع AMD Radeon 780M (iGPU، 1 GB مخصّصة)، ~16 GB رام → **CPU فقط عمليًّا**؛ يصلح لـ: التطوير، المعالجة، الاشتقاق، خطوط الأساس، ونماذج ≤8B GGUF (7B ≈ 5–15 ث/رسالة). توصية: WSL2 + Ubuntu لمطابقة بيئة لينكس.
- **Colab:** T4 (15 GB) مؤكّد بـ nvidia-smi، CUDA 13.0 (يُراعى عند اختيار عجلة llama-cpp-python). L4/A100 بوحدات مدفوعة لاحقًا.
- **GCP:** الـ bastion (e2-medium، لندن، ~36$/شهر بلا فائدة) **حُذف** مع قرصه؛ IP addresses فارغة؛ firewall افتراضيّ فقط. يُتحقّق من Billing Oct 7 ≈ 0$. تنبيه ميزانيّة 30$ موصى به.
- **تقدير الحمل:** ~60k استدلال كاملة؛ على المسار B: الصغيرة على الجهاز (~40 س على ليالٍ)، الكبيرة على Colab (~100–150 وحدة ≈ 10–15$).

---


## 11b. مستودع الرسالة (LaTeX / GitLab) — الحقائق الثابتة (2026-10-18)

- **المستودع:** `https://gitlab.com/jbj-theses/2026_bakhit_mashan-thesis` → محلّيًّا `C:\Users\dohaq\Documents\2026_bakhit_mashan-thesis`. بناء بـ `make` → `thesis.pdf`؛ مراجعة الدكتور بـ `make diff REV=ORIG_HEAD`. **أغلق thesis.pdf في Acrobat قبل make.**
- **قاعدة البنية (دليل الطالب + ردّ الدكتور 2026-10-19):** `\chapter` و`\section` وlabels الفصول و`\input` ثابتة. **`\subsection` حرّة** (إضافة/تسمية/ترتيب/حذف، ولها labels خاصّة بنا بادئة `sec:`) — نصّ الدكتور: "You can change \subsections but not \sections (structure)". استبدال محتوى شكل/جدول نائب مع إبقاء label **مسموح** (داخل القسم). `CLAUDE.md` في جذر المستودع يحمل القواعد.
- **Labels:** الفصول فقط: `ch:intro`, `ch:lit`, `ch:system`, `ch:eval`, `ch:conclusion`. لا labels للأقسام → إحالات الأقسام نصّ عاديّ («Section 1.6»). استثناء موافَق عليه: `sec:threat-model`. أشكال/جداول القالب لها labels (`fig:intro-overview`, `tab:rq`, `fig:architecture`, `tab:results`, `eq:score`…).
- **المراجع:** `reference.bib` (مفرد)، biblatex + biber، نمط APA. أوامر: `\parencite{key}` = (Author, Year)، `\textcite{key}` = Author (Year). 33 مدخلًا، مفاتيح = اسم المؤلّف الأوّل + السنة (`kim2025a` طبّيّ، `kim2025b` وكلاء الويب). أرقام المقالات في `eid`.
- **الاختصارات:** حزمة `acronym`، ملفّ `frontmatter/abbreviations.tex`؛ لا يظهر اختصار في القائمة إلا عبر أوامر الحزمة. LLM مضاف. الباقي (AI, API, GGUF, NLI, TF-IDF, CoT…) دفعة واحدة بعد الفصل 2.
- **الأشكال:** مجلّد `figures/`، تسمية `chNN_<name>_eng.png`، PNG ملوّن بأسلوب مائيّ (كأسلوب الدكتور)، ≈2096 بكسل عرضًا، `width=\textwidth`، تعليق بصيغتين (قصير لقائمة الأشكال + طويل يبدأ بالعنوان الغامق). Figure 1.1 = خريطة الفصول الخمسة (مولَّدة من الوصف الذي أعددته). أشكال 2.x و3.1 تُعاد بالأسلوب نفسه في وقتها.
- **قالب الفصول 3–5 (مُلزِم):** الفصل 3 «Methodology and Proposed System»: 3.1 Intro · 3.2 Research Methodology · 3.3 System Requirements (3.3.1 Functional, 3.3.2 Non-functional) · 3.4 System Architecture · 3.5 Components and Design · 3.6 Proposed Algorithm · 3.7 Implementation Details · 3.8 Summary. الفصل 4 «Evaluation and Results»: 4.1 Intro · 4.2 Experimental Setup (4.2.1 Environment, **4.2.2 Dataset**) · 4.3 Evaluation Metrics · 4.4 Baseline Methods · 4.5 Results · 4.6 Comparison with State of the Art · 4.7 Discussion · 4.8 Threats to Validity · 4.9 Summary. الفصل 5: 5.1 Summary · 5.2 Answers to the RQs · 5.3 Contributions · 5.4 Limitations · 5.5 Future Work · 5.6 Concluding Remarks.
- **إعادة توزيع خطّة الفصل 3 القديمة:** §3.2 Data (المعتمد) → **4.2.2** · Metrics/Statistics → 4.3 · Baselines → 4.4 · Environment → 4.2.1 · Figure 3.1 pipeline → 3.4 · وحدات الكود → 3.5 · إجراء اشتقاق المتغيّرات/الكشف كـ pseudo-code → 3.6 · المستودع/GGUF/Colab → 3.7. **الفصل 3 يبدأ بجملة صريحة:** the proposed system is an evaluation framework, not a new detector.
- **الفصل 2 — القرار:** الخيار ب، **سبعة أقسام فرعيّة**: 2.1 Introduction (= الفقرة الافتتاحيّة القديمة) · 2.2 Background Concepts {2.2.1 Phishing and Spear-Phishing ← 2.1؛ 2.2.2 Conventional and ML Approaches ← 2.2} · 2.3 Related Work {2.3.1 Offensive ← 2.3؛ 2.3.2 Defensive ← 2.4؛ 2.3.3 Open vs Proprietary ← 2.5؛ 2.3.4 Prompting ← 2.6؛ 2.3.5 Datasets, Metrics, and Evaluation Practices in Prior Work ← 2.7} · 2.4 Comparative Analysis (2.8 ف1، ف2، ف4 + Table 2.1 + الملاحظة) · 2.5 Research Gap (2.8 ف3 الخصائص الثلاث، Nahmias، Paladin، فقرة الأسئلة) · 2.6 Chapter Summary ← 2.9. الشكلان يحتفظان برقميهما. إحالات تتغيّر: المقدّمة (7 أرقام + الجملة الأخيرة)، 2.3.2 ف2 «Section 2.2»→2.2.2، 2.3.2 ف6 «Section 2.8»→2.4 و2.5، 2.3.4 ف2 «Section 2.4»→2.3.2، ملاحظة الجدول «Section 2.5»→2.3.3، الملخّص «Section 2.8»→2.4 و2.5 + الجملة الأخيرة لقالب الفصلين 3/4. فقرة الجدول تحتاج افتتاحًا جديدًا يعرّف الخصائص الثلاث (لأن فقرتها انتقلت إلى 2.5). تعديلات Pajola #5–#7 وKim #8 تُدمج في المرور.
- **حالة الصبّ:** الفصل 1 كامل (`1dae8ff`)، الفصل 2 كامل (`f3a3438`). Figure 1.1 = خريطة الفصول الخمسة (PNG مائيّ مولَّد). التالي: الفصل 3 على قالب «Proposed System». Word يبقى المرجع للمراجعة؛ كلّ تعديل يُطبَّق في النسختين.
- **أوامر Claude Code الثابتة:** الأمر 1 (ملء قسم) / الأمر 2 (إضافة فرعيّ موافَق عليه) / الأمر 3 (تسليم). commit بعد كلّ قسم، push في آخر الجلسة، لا تعديل أثناء مراجعة الدكتور.

---

## 12. مسودّة §3.1 (بانتظار المراجعة)

**Chapter 3: Methodology**

**3.1 Research Design Overview**

This chapter sets out how the questions posed in Chapter 1 are answered. The study is a quantitative, comparative evaluation: it builds no new detector, but measures how well existing open-source language models perform when prompted to classify email as spear-phishing or legitimate, under controlled variation of three factors. The design follows the logic of a benchmark rather than of a system paper, in the sense established by prior evaluations of language models as phishing detectors (Heiding et al., 2024; Nasution et al., 2025), with two differences that follow from Chapter 2: the detectors are open models run on self-managed infrastructure, and the target is AI-generated spear-phishing email.

Three factors are manipulated. The first is the detector model, since the second research question asks how open models compare with one another and with conventional baselines; several open-weight models of different sizes and families are evaluated under identical conditions (Section 3.3), alongside classical and neural baselines trained in the manner of prior work (Section 3.5). The second is the prompting strategy, since the third research question asks whether the way a model is instructed changes its performance; a zero-shot prompt serves as the reference condition against which prompt-engineered variants are compared (Section 3.4). The third is the input condition, since the fourth research question asks how far performance holds when messages are deliberately altered; each spear-phishing email is evaluated in its original form and in paraphrased and obfuscated forms derived from it at defined intensities (Section 3.2.3). The dependent variables are the classification measures introduced in Section 2.7: accuracy, precision, recall, F1, and false positive rate, computed per model, per prompting strategy, and per input condition, together with the change in each measure between the original and altered conditions, which is the robustness measure for the fourth question (Section 3.7).

The evaluation data are assembled from published research datasets rather than generated for this study, a choice made deliberately and discussed in Section 3.2. The core test set is the collection of LLM-generated spear-phishing emails released by Nahmias et al. (2024), which has the advantage of being the dataset used by the study identified in Section 2.8 as the most closely related, so that the results obtained here can be set directly against theirs; legitimate and traditional phishing email come from the Enron and SpamAssassin corpora that accompany it. A second, larger set of LLM-generated phishing and benign email, E-PhishLLM (Pajola et al., 2025), is used separately to examine whether findings on the core set generalize to a more varied collection; it is reported apart from the core results rather than merged with them, for reasons set out in Section 3.2.1.

Two design decisions follow directly from the threat model in Section 1.2.1. First, the paraphrased and obfuscated variants are produced before, and independently of, any detector being run, so that no transformation is tuned against a particular model; this is the black-box, non-adaptive setting the threat model specifies. Second, the detectors receive the subject and body text of each email and nothing else: no sender metadata, headers, URLs, or attachments, consistent with the scope in Section 1.6. In the Nahmias et al. (2024) data this requires stripping the HTML markup in which bodies are stored, and in E-PhishLLM hyperlinks are already replaced by a placeholder token; both steps are described in Section 3.2.2.

The experimental procedure is organized as a single pipeline, summarized in Figure 3.1. Published datasets are assembled and normalized to a common text representation; variants are derived from the spear-phishing emails and checked for preserved meaning; each email, in each condition, is presented to each model under each prompting strategy with fixed decoding settings; the model's free-text output is reduced to a binary label by a deterministic rule; and the resulting labels are scored against ground truth and compared across factors. The same pipeline, with the prompting stage replaced by training and inference, produces the baseline results. Every stage records the information needed to rerun it, which Section 3.8 specifies, because the reproducibility claimed in Section 2.8 depends on it.

Table 3.1 maps each research question to the objectives it serves, the factor manipulated to answer it, the measures reported, and the section of this chapter in which the relevant design is specified.

Table 3.1. Mapping of research questions to objectives, manipulated factors, measures, and chapter sections.

| RQ | Objectives | Manipulated factor | Measures reported | Section |
|---|---|---|---|---|
| RQ1 Effectiveness | O1, O3, O4 | None (all models, reference prompt, original inputs) | Accuracy, precision, recall, F1, FPR | 3.6, 3.7 |
| RQ2 Comparison | O2, O4 | Detector model; conventional baselines | Same measures; paired comparison across models and against baselines | 3.3, 3.5 |
| RQ3 Prompting | O3 | Prompting strategy (zero-shot vs. prompt-engineered) | Same measures; change relative to zero-shot | 3.4 |
| RQ4 Robustness | O1, O5 | Input condition (original, paraphrased, obfuscated, by intensity) | Same measures per condition; degradation relative to original | 3.2.3, 3.7 |

The remainder of the chapter follows the order of the pipeline. Section 3.2 describes the datasets and the derivation of variants; Section 3.3 justifies the selection of models; Section 3.4 specifies the prompting strategies; Section 3.5 describes the baselines; Section 3.6 gives the experimental procedure; Section 3.7 defines the measures and statistical comparisons; Section 3.8 documents the environment and the provisions for reproducibility; and Section 3.9 addresses the ethical considerations that arise from working with phishing content.

---

## 13. الخطوة التالية

1. ملاحظات سلبيّة على §3.1 (أو اعتماده).
2. كتابة **§3.2** (3.2.1–3.2.4) بأرقام البيانات المؤكّدة.
3. بعد اعتماد §3.2: تسليم هيكل المستودع + `01_download_data.py` + `02_preprocess.py` مختبَرَين على البيانات الحقيقيّة (باك-إند llama.cpp/GGUF، إعدادات local/cloud).
4. pilot على الجهاز (نموذج صغير، 20–50 رسالة) → حقائق لـ §3.3/3.6/3.8.
