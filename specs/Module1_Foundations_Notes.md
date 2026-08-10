# Module 1 — Foundations of Agentic AI & LLM Capabilities
**Instructor:** Prof. Amir Barati Farimani (Carnegie Mellon)
**Lab/TA support in chat:** Peter Pak, Hitesh K
**Session length:** ~2h00m
**Sources:** lecture transcript + Zoom chat log (the chat carries a lot of Q&A that never reached the audio)

The arc: define an agent → explain what an LLM is and how it got built → explain why scale unlocked it → survey the model landscape → close on prompt engineering.

---

## 1. What Is an Agent?

- **An agent is an intelligent system that observes an environment, receives feedback, and takes actions** — autonomously, without human intervention at each step.
- Examples of environments: a Roomba's physical space, Atari games, a PDF textbook, a CFD solver, a dataset on disk, Python interfaces and APIs.
- **Contrast with a chatbot:** a chatbot is an interface you send prompts to. An agent acts on an environment and consumes the resulting feedback.

### The five components

| Component | Meaning | Example |
|---|---|---|
| **Observation** | What the agent perceives | Sensor data, a text file, an Excel sheet, tool output, multimodal data |
| **Action** | What it can do | Call an API, launch a calculator, run a weather app, search the web |
| **State** | Memory | "How did I answer this email before?" |
| **Transition dynamics** | How state changes given feedback | — |
| **Feedback / reward** | Quality signal from the environment | A simulation log file, an error trace |

### The four interaction modes

If asked what an agent does, these four: **memory**, **reasoning** (chain of thought, reflection, self-critique, decomposition), **tool use** (calendar, calculator, code interpreters, search, image databases, even software like Photoshop — hardware and software both), and **actions**.

### Types of actions
Generate text • call an API (e.g. a bank's mortgage-rate code) • edit files and fix bugs • query databases • drive simulation engines • send messages • look up references • control instruments • update configurations • monitor devices.

### Evolution of agents (as presented)
1. **2020** — simple LLMs: text in, text out
2. **2022** — extended context windows
3. **2022** — tool use discovered (weather, calendar, calculator)
4. **2023** — memory: search and learn from stored context
5. **2024–25** — autonomous agents: goal + memory + tools + actions across web, APIs, databases, files, devices
6. **Future** — orchestration layer, multiple agents cooperating, self-learning loops and reflection

### Why this matters commercially
A widely cited industry forecast holds that **by 2028 roughly a third of enterprise software applications will incorporate agentic AI**, up from a very small base today. *(Attributed in the lecture to industry analysis; the transcript garbles the year — see appendix.)*

---

## 2. What Is a Language Model?

- A **statistical model that builds a mathematical representation of language** — grammar, syntax, and context. It's what lets a model distinguish *bank of a river*, *JP Morgan Bank*, and *blood bank* from context alone.
- Formally: **a probability distribution over sequences of tokens.** "The capital of France is ___" → the model scores every word in the vocabulary and finds *Paris* has the highest probability.
- **Autoregressive**: predict the next token, append it, then predict the next given everything before.
- Mechanically: the network takes "I saw a cat on a," applies a **softmax** over the whole vocabulary, and selects the highest-probability entry (*mat*).
- **Crucially, no grammar rules are supplied.** We don't tell the model that a verb follows a subject. It learns patterns, context, and semantics purely from data.

### Poll — why does next-token prediction produce semantic understanding?
**Answer: correct prediction requires modeling context and structure.** To reliably predict *Paris*, the model must hold a working representation of meaning. Semantics is a *consequence* of the prediction objective, not a separate feature.

Follow-up in chat (Tochi E.): is that modeling done during training or at response time? — During training; applied at generation.

---

## 3. History: Why ChatGPT Couldn't Have Been Built Earlier

| Era | Approach | Why it failed |
|---|---|---|
| **1966** | Hand-coded rules (ELIZA-style) — "adjective before noun," etc. | Language has too many rules, exceptions, and long-range dependencies |
| **1980s** | Statistical n-gram counting | Works for ~4–5 words of context; beyond that it becomes a statistical bottleneck |
| **1990s–2010s** | RNNs and LSTMs — genuine sequential modeling via backpropagation through time | **The sequential bottleneck** |
| **2017** | Transformers | — |

### The sequential bottleneck (the key idea)

- RNNs learn by multiplying partial gradients along the sequence.
- If any one of those gradients is very small, **it kills the learning signal for the whole chain**. Try to summarize a Shakespeare play with thousands of words and one small multiplier destroys everything.
- This is the vanishing-gradient problem, and it's why LSTMs (1997) never scaled to ChatGPT-class models.
- **Poll — why don't RNNs/LSTMs scale?** Answer: **sequential computation and memory bottleneck.** Vanishing gradients is *part* of this, not the whole story — the word "only" in the distractor option is what makes it wrong.

### 2017 — *Attention Is All You Need* (Google)

- Every word connects **directly** to every other word, with a learned weight, without passing through the words in between.
- Sequences are modeled **in parallel rather than sequentially**. This is the paradigm shift.
- Mechanism: **multi-head attention** over **K, Q, V** (keys, queries, values).
- Worked example: *"The animal didn't cross the street because it was too tired."* Attention resolves *it* by assigning a strong weight to *animal* and weaker weights to *street*, *was*, *tired*.
- **Poll — what does self-attention allow?** Answer: **attend to any token regardless of position.**
- This is the **T** in GPT.

---

## 4. Building a Language Model — Four Steps

**1. Tokenization.** Machines take numbers, not text. A tokenizer maps each piece of text to an integer. **Byte-pair encoding** is the workhorse: it splits words into meaningful sub-units, so *management* → *manage* + *ment*. The payoff is that the model learns morphological function — *-er* makes agent nouns (tokenizer, driver, manager), *-ment* forms nouns from verbs — and generalizes across words it hasn't seen whole.

**2. The transformer engine.** Encoder learns representation and context; decoder predicts the probability of the next token. Highly parallelizable — you can feed it as much data as you have.

**3. Pre-training — the P in GPT.** This is the second breakthrough, alongside attention.

- Ordinary supervised learning needs labeled data (X and Y), and labeling is expensive and slow.
- **Masked language modeling** (introduced by Google with BERT) removes that constraint: take any sentence off the internet, blank out a word, and predict it. *"My dog is ___"* → the label is *hairy*, and it came free with the sentence.
- Mask the other position instead — *"My ___ is hairy"* → *dog* — and you have another training example from the same sentence. **The combinatorics of masking × the size of the internet is effectively unbounded.**
- **Self-supervised**: no human labeling, no human intervention. Every major lab is running this continuously.
- **Data sources:** the internet, broadly — arXiv PDFs, Pile-CC, book collections, GitHub code, OpenWebText, Wikipedia (a surprisingly small slice of the total).
- Contrast with domains where data *is* the bottleneck: measuring molecular toxicity can cost thousands of dollars per data point. Language has no such problem.

**4. The prediction head and the loss.** Cross-entropy loss increases the probability of the correct next token and decreases everything else; backpropagation adjusts the weights. **Poll answer:** minimizing cross-entropy means maximizing the probability of the correct next token.

> **Summary of the pipeline:** input text → tokenize → transformer (encoder/decoder) → prediction head → repeat over all data.

---

## 5. Scaling Laws — Why Models Got Enormous

### The GPT-2 observation (2019)

OpenAI's thesis: **stop building a separate model per task.** One model should summarize, answer questions, and classify. GPT-2 was transformer-based, open-sourced, with a context window of 512–1024 tokens and multiple size variants topping out at **1.5B parameters**.

Two findings emerged: making the model somewhat larger improved understanding and reasoning, and **larger + more pre-training made the model spontaneously multi-task**.

### The GPT-3 bet (2020)

> *"If a 10× increase in parameters yielded better generalists, what would a 100× increase unlock?"*

- **What a parameter is:** in `y = ax + b`, *a* and *b* are the two parameters of a line. A 175B-parameter model has 175 billion such numbers. As the professor put it later — **weights are just numbers**, huge matrices of them, randomly initialized and then nudged by backpropagation.
- They trained 8 model sizes, the largest at **175B parameters**, for roughly **$4.5M**.
- **The result:** with only a handful of examples, the 175B model's accuracy climbs sharply — ~65% on math problems with ten examples — while 1.3B models stay near zero. Few-shot capability *emerged* at scale.

### The lesson
- **Scale beats complexity.** What matters in the long run is leveraging computation.
- Larger models unlock emergent capabilities: multi-task learning, reasoning, logic, tool calling.
- **Poll — what do scaling laws tell us?** Answer: **performance improves predictably with scale.**
- **The recipe of intelligence:** data (the whole internet) + pre-training (harvests it without labels) + scaling law (predicts the payoff). Strategy: don't guess — train small, extrapolate with the laws, then commit to one massive run.
- Critically: **before pre-training and transformers, the scaling law didn't hold.** You could build a 100B-parameter LSTM and get nothing. All three ingredients were required.

**Reference shared in chat** (Jaszeer): *Scaling Laws for Neural Language Models*, arXiv:2001.08361.

### Q&A — why still do the massive run? (danmills)
*If scaling laws are predictable, why not train small and extrapolate?*

Because a larger model is larger **capacity**, and capacity has to be filled. Twenty containers need more to fill them than five. **Compute, data, and parameters must all scale together** — a huge parameter count trained on too little data performs at the level of the data it saw.

---

## 6. The Model Landscape

### Closed vs. open
- **Closed-weight:** OpenAI, Google, Anthropic — the weights are not published.
- **Open-weight:** Meta, Mistral, and several Chinese labs (DeepSeek, Kimi) publish weights you can download and fine-tune.
- **The privacy argument** for open weights: if you can't send customer data to a third-party API, download an open model and fine-tune it on your own domain. A dedicated course module covers this.

### Which model for which job (the selection heuristic)

| Need | Choice |
|---|---|
| Complex reasoning (math, physics, Olympiad-style) | **Claude** |
| General-purpose, coding, easy interfacing | **GPT** |
| Multimodal — images, video, audio, long-context understanding | **Gemini** |
| Real-time data (news, social) | **Grok** |
| Fine-tuning on your own data / privacy | **Llama, Mistral** — open weights |
| Tool use specifically | GPT rated strongest; Claude rated strongest for agentic reasoning |

**Poll — a repository of CAD files, PDFs, images, and source code. Which model?** Answer: **Gemini**, on multimodal breadth.

**Poll — which statement reflects the current state of frontier LLMs?** Answer: **most frontier models now offer ~1M tokens of context or more, and effective context utilization is becoming the key differentiator.** The distractors are all false: Claude no longer uniquely has the largest window, all frontier models are multimodal, and open-source models remain very competitive.

> The lecture's specific version numbers were already contested by participants during the session and are best treated as a snapshot — see appendix.

---

## 7. Context Windows — Advertised vs. Effective

- **Definition:** how many tokens a single active session can hold and process.
- Scale intuition: 1M tokens is roughly the length of an entire major book series. The original transformer paper worked with ~512 tokens.
- **The industry has largely settled on ~1M as sufficient** for reasoning; going further is possible but arguably unnecessary.

**The important caveat — advertised max ≠ effective context.** Two phenomena degrade long contexts:
- **Attention sink** — models over-attend to the first few tokens of the prompt.
- **Lost in the middle** — content in the middle of a long prompt gets ignored.

**Rule of thumb given: only ~50–60% of the advertised window is realized in practice.** (Daniel Ramos raised this in chat as 50–65%; Peter confirmed and pointed to lost-in-the-middle.)

Also from chat (Juan Hernandez): **tokens are not words.** The mapping is not 1:1.

---

## 8. Evaluation

- Evaluation must be **holistic** across knowledge and reasoning (MMLU), specialized domains (LegalBench, MedQA), core skills (math), coding (LiveCodeBench), search, and hallucination rate — plus **cost per million output tokens**.
- **MMLU** = Massive Multitask Language Understanding.
- **Poll — why is LLM evaluation difficult?** Answer: **intelligence varies across tasks and domains.** Math reasoning differs from physics, from astronomy, from biology. No one judges a model on a single task.
- **Data contamination** is the central methodological risk: benchmark answers leaking into training data.

### Q&A on contamination
**Ayush Agrawal:** benchmarks are on the internet — how is contamination prevented?
**Answer:** the labs run leakage and sanity checks before training. But pressed further, the professor was candid: **there is no regulatory body verifying this**, and nobody outside the labs can confirm it. He expects some form of international oversight eventually.

**Ayush follow-up:** are there non-deterministic benchmarks that can't be gamed? — "I'm not aware." *(Note: time-gated benchmarks like LiveCodeBench, which appeared on his own evaluation slide, exist partly for this reason. Worth following up.)*

### Q&A on AI-generated data (Doerte Doepfer, expanded by Gurleen Singh)
*Does AI-generated text contaminating the internet degrade future training?*

- Large teams at each lab work full-time on data cleaning — not only for AI-generated content but for factually bad content generally (the flat-earth example: if enough sites assert it, the model can learn it).
- The professor was honest about uncertainty on the AI-generated question specifically, and offered a counterpoint: generated text is often cleaner than human text. Doerte's rejoinder — *less noise, but it averages everything out* — got agreement that bias compounding is a real concern.
- **His broader claim:** data is no longer the bottleneck. Labs are largely re-training on the same clean corpora with different masking combinatorics, and **the current focus has moved to feedback loops (RLHF) and mixture-of-experts approaches** rather than new data.

---

## 9. Prompt Engineering

**Anatomy of a good prompt:**
- **Instruction** — directive, with an action verb: *summarize this*, *generate that*
- **Primary context** — the material to be processed
- **Examples** — few-shot pairs. *"Always"* provide these when designing agents.
- **Cue** — a jump-start prefix constraining the output format (*output only the temperature in Fahrenheit*; *answer only yes or no*)

**Worked contrast:**
- Weak: *"Write an introduction for a weekly newsletter."*
- Engineered: *"Write an introduction for Contoso's weekly newsletter. Mention last week's all-hands, thank the team for their hard work over the past few months, include a positive outlook for the coming quarter, and sign as the senior leadership team."*

**Few-shot in a domain — the loan approval example:** supply two or three prior decisions with their credit history, credit score, and outcome (approved $500K, declined $600K). Those examples do most of the work.

**Token efficiency matters** because agents send prompts back and forth thousands of times, on API not GUI. If a JSON structure repeats keys on every row, use a **markdown table** instead — same information, far fewer tokens.

**The cheat sheet:**
- Be specific; leave no room for interpretation
- Be descriptive; use analogies to convey the intended register
- **Double down** — repeat key instructions before *and* after the content
- **Order matters** — put critical information at the start or the very end (this is a direct consequence of lost-in-the-middle)
- **Grounding** — provide source data and ask for citations

---

## 10. Poll Summary

| Question | Answer |
|---|---|
| What distinguishes an agent from a chatbot? | Ability to act on an environment and receive feedback |
| What qualifies as an environment for an LLM agent? | All of the above (PDF textbook, CFD solver with an API, dataset on disk) |
| Which action requires tool use rather than pure language modeling? | Running a finite element simulation |
| Why does next-token prediction yield semantic understanding? | Correct prediction requires modeling context and structure |
| Why don't RNNs/LSTMs scale? | Sequential computation and memory bottleneck |
| What does self-attention allow? | Attend to any token regardless of position |
| Minimizing cross-entropy loss means… | Maximizing the probability of the correct next token |
| What do scaling laws tell us? | Performance improves predictably with scale |
| Best model for CAD + PDFs + images + code? | Gemini (multimodal) |
| Current state of frontier LLMs? | ~1M context is standard; effective utilization is the differentiator |
| Why is LLM evaluation difficult? | Intelligence varies across tasks and domains |
| When does a language model become an agent? | When it can use tools, interact with an environment, and receive feedback — autonomously |

---

## 11. Chat-Only Q&A Worth Keeping

**Gerardo Bodegas Martinez — isn't a chatbot also getting feedback when it asks the user for clarification?**
Peter's answer: the poll contrasted a *simple* chatbot with no environmental interaction. Modern chatbots do get user feedback; the distinguishing property of an agent is interacting with and learning from an **environment**. Ayush Agrawal added the practical framing: an agent automates the intermediate steps a user would otherwise perform by hand — copying file contents, pasting results.

**Kinshuk Dudeja — how do we define a tool?**
Peter: *a function call that a large language model is capable of performing.* Karthik Venkatachalam expanded: any external capability — APIs, databases, search engines, calculators, code execution, simulators.

**Antonysamy Joseph — do agents reason, or does the LLM?**
The **LLM** does the reasoning; the agent supplies the structure around it (goals, memory, tools, actions, feedback loops).

**Sadhiesh Babu Dhandapani — is the progression LLM → reasoning model → agent?**
Peter treated "agent" as the broad term for an LLM that reasons *and* uses tools to interact with an environment.

**Ayush Agrawal — do models like ChatGPT use only the decoder?**
Yes. Research showed decoder-only scales successfully, and frontier models moved that way. *(Worth noting this partly supersedes the encoder/decoder framing in the slides.)*

**Kinshuk Dudeja — are general-purpose models beating specialized ones?**
Peter: specialized models are usually better on specific use cases, because they hold data not available to general models.

**Tochi E. — when are larger models not better?**
Mostly a resource-constraint question. Larger is usually better, but a smaller model often suffices for a narrow task at much lower inference cost.

**Renjith — is there a hard technical limit on parameter count?**
No hard limit — the constraints are practical: VRAM (the model must fit on the GPU), compute, energy, data, and cost.

**Dimple — how do models avoid hallucination?**
Covered across the course through **tool use, RAG, and fine-tuning**.

**Ifeanyi Enwezor — will we cover QLoRA?**
LoRA gets a conceptual briefing in a lab; quantization is treated as a configuration detail rather than a topic.

**Sarita Inguava — parameters vs. model dimension?**
Two distinct things. **Context window** = how many tokens fit in one sequence. **Model dimension (d_model)** = the matrix dimension inside multi-head attention; for d_model = 768 the K matrix is 768×768. d_model drives parameter count; context window drives sequence length.

**Praveen Komarraju — how many attention heads, and how is that chosen?**
One head is insufficient to capture the different functions of language. Head count scales with d_model; **head size = d_model ÷ number of heads.**

**Ifeanyi Enwezor — walk through backpropagation.**
Compressed version given: the loss function measures the distance between prediction and ground truth; that error is distributed back over all weights via partial gradients. If the true next word is *cat* with target probability 1 but the model outputs 0.6, the 0.4 gap is back-propagated and the weights nudged, so the next iteration gives 0.7, 0.8, 0.9. Repeat across all training samples.

**Juan Hernandez — Google's vector-search compression work?**
Compression and reduction techniques (including LoRA-family methods and quantization) are covered in the fine-tuning module. Motivation: frontier-size models can't be loaded on local GPUs — only labs with large A100/H200 fleets can.

**Shawn Cunningham — why mixture of experts over alternatives?**
Deferred to the next module. **The explanation given in this session appears to describe a different technique entirely — see appendix.**

---

## 12. Appendix: Transcript Artifacts, Errors, and Claims to Verify

This lecture covers a lot of ground quickly and contains more to double-check than the later sessions. Sorted by how much it matters.

### Substantive concerns

- **The mixture-of-experts explanation looks incorrect.** As described: generate ~10 responses each from several models, have an evaluator model rank all 30, then train a head to produce the rank-1 response. That describes **best-of-n sampling with a reward model** — the RLHF/rejection-sampling family — not mixture of experts. MoE is a *sparse architecture* in which a router gates each token to a small subset of expert feed-forward subnetworks inside a single model, cutting active compute per token. These are different ideas at different layers of the stack. Verify against the Module 2+ treatment before using this in any writeup.

- **Parameter counts for GPT-4 and later are presented as fact but are not public.** "GPT-4 with 500 billion," "GPT-4.5 with 1 trillion," a "2 trillion parameter model," and later "ChatGPT 5.6 is… 100 trillion numbers" — OpenAI has never disclosed these. Treat as rumor. GPT-2 (1.5B) and GPT-3 (175B) *are* published and correct.

- **"The probability of 'the cheese ate the mouse' is the maximum."** This inverts the point being made — *the mouse ate the cheese* should be the higher-probability sentence. Almost certainly a misspeak or transcription flip, but as stated it contradicts the slide's purpose.

- **Attention scaling factor.** The transcript says you divide by "D" / "DS squared." The actual attention equation divides by **√d_k** (square root of the key dimension). Worth stating correctly.

- **Flat Earth Society membership "10 million subscribers"** — off by orders of magnitude. The point about bad data contaminating training stands regardless; the number doesn't.

- **"AI came in 1980"** — the field dates to the 1956 Dartmouth workshop. The 1980s reference likely means the statistical-NLP era being discussed.

- **The claim that non-deterministic/contamination-resistant benchmarks may not exist.** Time-gated benchmarks (LiveCodeBench, which appears on the evaluation slide) exist substantially for this reason. The professor's "I'm not aware" was honest but the answer is on his own slide.

### Dates and versions

- **GPT-2 release**: stated as both 2019 and 2020 in the same passage. **2019** is correct.
- **Transformer paper**: stated as 2017 in most places, 2018 once. **2017** is correct. BERT is 2018.
- **"By 2028… will be implemented by 2020"** — transcription slip; the forecast year is 2028.
- **Model version numbers were contested live in chat.** The slide claimed Opus 5; Juan Hernandez posted that Opus 5 wasn't out and the current release was 4.8. Shawn Cunningham noted a Mythos/Fable naming change. Gemini is cited as 2.5 Pro in one place and 3.1/3.5 elsewhere. The slide is dated "July 2026" in one breath and "as of May 2026" in another. **Treat every specific version number in this deck as a snapshot that was already stale during delivery.**
- **Manish Bhatt's chat correction** distinguishing GPT-4 (2023) from GPT-4o is worth noting; the lecture refers to "GPT-4.0 in 2023," which conflates the two.

### Approximations stated as facts

- **"1M context = all Harry Potter / all Shakespeare books"** — right order of magnitude, but both corpora exceed 1M tokens. Fine as intuition, not as a figure.
- **"Effective context is 50–60% of advertised"** — a working heuristic, not a measured constant. It varies by model, task, and where in the window the needed information sits.
- **"Attention paper context window was 512 words"** — approximately the sequence lengths used in the paper's experiments; not a property of the architecture.
- **"Byte-pair encoding is the best tokenization technique"** — BPE is dominant, but SentencePiece, WordPiece, and unigram methods are all in production use. "Best" is a preference.
- **"$4.5M to train GPT-3"** — matches commonly cited estimates. Reasonable.
- **"300 engineers working on data quality," "$2,000–3,000 per molecular toxicity data point"** — plausible anecdotes, unverified.

### Transcription garbles

- "Adari Games" → **Atari**
- "Entropy" / "Entropic" → **Anthropic**
- "Cloud" / "Clot" → **Claude**; "LLMO" / "Lomo" / "LLMA" → **Llama**
- "Olamiad" → **Olympiad**
- "Doyommen" → almost certainly **GPQA Diamond** (the "Google-proof" PhD-level Q&A benchmark)
- "Bibilotech" → **Bibliotik**; "PileCC" → **Pile-CC** (both components of The Pile)
- "Coro and LoRa" → **QLoRA and LoRA**
- "Major Language Model" → self-corrected to **Massive Multitask Language Understanding**
- "loss in the middle" → **lost in the middle**
- "mass language model" → **masked** language model, throughout
- "scaling log" → **scaling law**; "performance improves predictability" → **predictably**
- "Contoso" is Microsoft's standard fictional company used in documentation examples — not a real client (danmills' joke in chat, which several people caught)
- "before that we had LLMO… in which it was directional" → ambiguous; likely either **ELMo** or unidirectional GPT-1-style LM. The contrast being drawn (unidirectional → BERT's bidirectional) is sound either way.
