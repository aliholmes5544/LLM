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

## 4. حالة الفصل ١ (مكتمل، معتمد)

1.1 Introduction and Background · 1.2 Spear-Phishing and the Weaponization of LLMs · **1.3 Threat Model (جديد، نهائيّ)** · 1.4 The Detection Challenge · 1.5 Open-Source LLMs as a Prospective Detection Approach · 1.6 Problem Statement · 1.7 Research Aim, Questions, and Objectives · 1.8 Significance and Contributions · 1.9 Scope and Delimitations.

**Threat Model (§1.3) — المحتوى المعتمد:** goal (deliver + evade) · capabilities (LLM access without jailbreak [Saha Roy 2024]; automated reconnaissance [Hazell 2023; Czybik 2026; Kim 2025b]; refinement e.g. paraphrasing [Chen 2026]; obfuscation = study-defined controlled transformation) · knowledge = **black-box, non-adaptive** (plausible setting; consistent with Chen; matches design) · defender = open model, local, text only (subject+body), no fine-tuning · assumptions: generator not cooperative (generator-agnostic, vs Paladin), attacker non-adaptive · out of scope: adaptive/partial-knowledge attacker; prompt-injection against the detector.

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

## 7. التعديلات المؤجَّلة لجلسة التنسيق (10)

| # | الفصل | الموضع | التغيير |
|---|---|---|---|
| 1 | 1 | §1.9 | "produced within the study" → "drawn from published research datasets rather than generated within the study, and the paraphrased and obfuscated variants ... are derived from those emails as controlled transformations" |
| 2 | 1 | §1.7 O1 | إضافة "published" قبل AI-generated spear-phishing samples |
| 3 | 1 | عنوان §1.3 | النمط → Heading 3 (حاليًّا نمط لصق) |
| 4 | 1 | §1.4 | "section 1.2" → "Section 1.2" |
| 5 | 2 | §2.4 ف2 (آخرها) | إضافة: "More recently, Pajola et al. (2025) released E-PhishLLM, a dataset of LLM-generated phishing and benign emails built from synthetic user profiles, and evaluated a range of detectors on it, including two proprietary models prompted zero-shot; they report that detectors which perform near-perfectly on existing datasets perform much lower on E-PhishLLM, and the models they prompted were, again, proprietary." |
| 6 | 2 | §2.8 ف4 (بعد جملة Koide) | إضافة: "The zero-shot evaluation of proprietary models on LLM-generated phishing by Pajola et al. (2025) likewise leaves the open-model case untested." |
| 7 | 2 | Table 2.1 | صفّ قبل Pang: Pajola et al. (2025) / Proprietary (two, zero-shot) / ✓ / ✗ (LLM-generated phishing, not spear-specific) / E-PhishLLM; detectors perform much lower than on existing datasets |
| 8 | 2 | §2.5 | Kim et al. (2025) → (2025a) في موضعين |
| 9 | refs | — | إضافة Pajola |
| 10 | 1+2 | عامّ | عنوانا الفصلين: em dash → ":"، نمط Heading 1، إزالة رمز النقطة؛ توحيد أنماط المتن على Normal؛ Table 2.1 يُعرض صحيحًا لكن بنيته RTL (لا تغيّر اتّجاهه)؛ تحديث جدول المحتويات |

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

## 12. مسودّة §3.1 (بانتظار المراجعة)

**Chapter 3: Methodology**

**3.1 Research Design Overview**

This chapter sets out how the questions posed in Chapter 1 are answered. The study is a quantitative, comparative evaluation: it builds no new detector, but measures how well existing open-source language models perform when prompted to classify email as spear-phishing or legitimate, under controlled variation of three factors. The design follows the logic of a benchmark rather than of a system paper, in the sense established by prior evaluations of language models as phishing detectors (Heiding et al., 2024; Nasution et al., 2025), with two differences that follow from Chapter 2: the detectors are open models run on self-managed infrastructure, and the target is AI-generated spear-phishing email.

Three factors are manipulated. The first is the detector model, since the second research question asks how open models compare with one another and with conventional baselines; several open-weight models of different sizes and families are evaluated under identical conditions (Section 3.3), alongside classical and neural baselines trained in the manner of prior work (Section 3.5). The second is the prompting strategy, since the third research question asks whether the way a model is instructed changes its performance; a zero-shot prompt serves as the reference condition against which prompt-engineered variants are compared (Section 3.4). The third is the input condition, since the fourth research question asks how far performance holds when messages are deliberately altered; each spear-phishing email is evaluated in its original form and in paraphrased and obfuscated forms derived from it at defined intensities (Section 3.2.3). The dependent variables are the classification measures introduced in Section 2.7: accuracy, precision, recall, F1, and false positive rate, computed per model, per prompting strategy, and per input condition, together with the change in each measure between the original and altered conditions, which is the robustness measure for the fourth question (Section 3.7).

The evaluation data are assembled from published research datasets rather than generated for this study, a choice made deliberately and discussed in Section 3.2. The core test set is the collection of LLM-generated spear-phishing emails released by Nahmias et al. (2024), which has the advantage of being the dataset used by the study identified in Section 2.8 as the most closely related, so that the results obtained here can be set directly against theirs; legitimate and traditional phishing email come from the Enron and SpamAssassin corpora that accompany it. A second, larger set of LLM-generated phishing and benign email, E-PhishLLM (Pajola et al., 2025), is used separately to examine whether findings on the core set generalize to a more varied collection; it is reported apart from the core results rather than merged with them, for reasons set out in Section 3.2.1.

Two design decisions follow directly from the threat model in Section 1.3. First, the paraphrased and obfuscated variants are produced before, and independently of, any detector being run, so that no transformation is tuned against a particular model; this is the black-box, non-adaptive setting the threat model specifies. Second, the detectors receive the subject and body text of each email and nothing else: no sender metadata, headers, URLs, or attachments, consistent with the scope in Section 1.9. In the Nahmias et al. (2024) data this requires stripping the HTML markup in which bodies are stored, and in E-PhishLLM hyperlinks are already replaced by a placeholder token; both steps are described in Section 3.2.2.

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
