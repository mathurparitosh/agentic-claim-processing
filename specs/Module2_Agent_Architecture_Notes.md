# Module 2 — Agent Architecture: Memory, Tools, and Reasoning Loops
**Instructor:** Amir Barati Farimani (lab support: Peter, Jesse)
**Session length:** ~1h48m, including Q&A

The lecture has three pillars: (1) unlocking reasoning through intermediate steps, (2) the ReAct paradigm (reasoning + acting), and (3) memory architecture. A practical build checklist is at the end.

---

## 1. Why LLMs Fail at Multi-Step Reasoning

- **Root cause:** LLMs are next-token predictors. Semantic understanding emerges from that objective, but *serial* (step-dependent) problems break it.
- **Transformers operate at constant depth.** They process context in parallel via attention, so a problem requiring, say, five strictly sequential steps has no matching computational depth. The model either needs an impractically deep architecture or fails outright.
- **Motivating example (few-shot pattern failure):**
  - Given `Carnegie Mellon → EN` and `machine learning → EG`, the rule is *last letter of each word, concatenated*.
  - Asked for `deep learning`, the model often answers `EG` — copying the surface pattern instead of inferring the rule. The correct answer is `PG`.
  - **Takeaway:** humans infer rules; models mimic patterns.

### Two mechanisms that fix this

- **Decompose complexity (reduce cognitive load).** Don't dump the whole problem into one context. Break it into steps.
  - *Example:* 3 baskets with 12, 15, 9 apples; 10 given away. Step 1: sum = 36. Step 2: 36 − 10 = 26.
- **Create virtual depth.** A constant-depth transformer *can* handle inherently serial problems if it produces a sufficiently long intermediate reasoning sequence. Step-by-step output effectively extends reasoning capacity beyond the fixed architecture.

### Historical lineage (why this idea predates ChatGPT)

- **2017 — rationale generation:** work on math word problems (e.g., two trains crossing a platform in 27s and 17s, crossing each other in 23s → speed ratio 3:2) showed that writing out the rationale, not just the answer, is what makes these solvable.
- **2021 — verifiers:** a second model trained to check the integrity of the intermediate steps (the soda/party-counting style problems).
- **Scratchpad idea:** identical to elementary-school carry arithmetic — add 9 + 7, write 6, carry the 1. That written scratchpad can be handed to a language model as an instruction format.

---

## 2. Chain of Thought (CoT) — Few-Shot

- **Definition:** make your own mental process explicit in natural language, then hand that to the LLM as demonstrations.
- **Standard prompting** gives `question → answer` pairs. **CoT prompting** gives `question → reasoning steps → answer`. The model then mimics the reasoning structure on the new question.
  - *Classic example:* Roger has 5 tennis balls, buys 2 cans of 3 → "started with 5, 2 cans × 3 = 6, 5 + 6 = 11."
- **Reported gains** on math word problems in the source paper: roughly 33% → 55%, and 18% → 57% depending on benchmark. Largest gains are in math and complex reasoning.
- **How to apply it in your domain — give 2–4 worked examples of the actual procedure:**
  - *Radiology:* a radiologist narrates what they look at (high-density regions, blobs, location) and how they arrive at the diagnosis.
  - *Banking / credit limit increase:* credit score → missed payments → annual salary and raises → tax documents / W-2 → average monthly expenditure → approve or deny.
- **Main limitation:** it requires **task-specific, handcrafted examples**. A radiology agent's CoT doesn't transfer to loan approval. This handcrafting is the bottleneck.

---

## 3. Zero-Shot CoT — "Let's think step by step"

- **The idea:** find one task-agnostic prompt that unlocks reasoning across finance, IT, healthcare, engineering, math — with zero demonstrations.
- **The phrase:** appending *"Let's think step by step"* triggers multi-step reasoning without a single example.
  - *Same tennis-ball question:* standard zero-shot answers 28 (wild guess); with the trigger phrase it walks through 5 + 6 = 11.
  - Also works on state-tracking tasks (the coin-flip benchmark, where you must track heads/tails across several people flipping or not flipping).
- **Reported accuracy from the prompt-comparison table:**
  - "Let's think step by step" — ~78–80%
  - Other reasoning-flavored cues ("let's think about this logically", "let's be realistic") — still strong
  - Deliberately misleading or irrelevant cues ("it's a beautiful day", "let's count the number of A's") — degrade performance, but *still beat* plain zero-shot
  - Plain zero-shot (answer only) — ~17.7%
- **Emergence with scale:** the effect starts appearing around ~7B parameters and is strongly present at 175B (GPT-3 scale). It is a property of scale, not something small models can do.
- **Hierarchy of methods:** few-shot CoT (manual, domain-specific) > zero-shot CoT (zero human effort) > standard zero-shot. **Best practice: combine both** — open with "let's think step by step," then supply one or two domain examples.
- **Reasoning can be sound but still mismatch ground truth.** Example: "a pond with trees around it is likely located ___" → the model reasons correctly to *forest*; the labeled answer was *countryside*. Logic was valid, classification was off.

---

## 4. ReAct — Reasoning + Acting

**Core claim of the lecture:** reasoning alone is not enough, acting alone is not enough. The synergy is the agent.

### Reasoning only — two failure modes
- **Hallucination:** fabricates facts when internal knowledge is insufficient (e.g., anything after the training cutoff).
- **Error propagation:** one wrong step corrupts the entire chain, like a single bad line in an exam problem.
- **Key insight:** with no external resource, there is no validity check.

### Acting only — two failure modes
- **Aimless exploration:** tool calls fired on shallow triggers rather than a coherent plan (opening every kitchen drawer instead of reasoning that a knife is probably near the sink or the stove).
- **No sense-making:** cannot adapt the plan based on what an observation actually *means*.

### The loop
```
Thought → Action → Observation → Thought → Action → ... → Finish
```
- *Kitchen analogy:* Thought "I need to chop vegetables" → Action "open drawer" → Observation "drawer is empty, no knife" → Thought "find a replacement or look elsewhere" → …
- *Coffee analogy:* grind → dose → tamp → brew, and if the hopper is empty, you interrupt and refill. You think and act in alternation against a real environment.

### Case study: the Apple Remote query
*"Aside from the Apple Remote, what other device can control the program it was originally designed to interact with?"*

| Approach | Trace | Result |
|---|---|---|
| **Reason only** | "Apple Remote was designed for Apple TV; Apple TV is controlled by iPhone/iPad/iPod Touch" | **Wrong** (hallucinated premise) |
| **Act only** | search "Apple Remote" → search "Front Row" → not found → search "Front Row software" → stops at search cap | **Wrong** (no synthesis) |
| **ReAct** | Thought: find the original program → Act: search Apple Remote → Obs: designed for *Front Row* media center → Thought: now search Front Row → Obs: ambiguous (Front Row Motorsports, Front Row Software) → Thought: motorsports is irrelevant to Apple → Act: search Front Row Software → Obs: controlled by Apple Remote **or keyboard function keys** | **Correct** |

- The winning move is **dynamic planning**: the agent uses the observation from step 1 to pivot its strategy in step 2.
- **Also note:** acting loops need a **cap on iterations** (max search / max tool calls) as a safety valve.
- **What "environment" means here:** Python code, an Excel sheet, a Google search API, a weather API, financial software, a credit-scoring script, an SQL database. Acting = connecting the LLM to these.
- **Interview-ready answer:** the best paradigm for agent design is **ReAct**.

---

## 5. Memory

### The problem
- **LLMs are stateless.** Each API call is a discrete, isolated event. The "memory" you experience in ChatGPT is an **illusion created by the application layer**, which resends the entire conversation history with every new prompt.
  - *Demo:* "Hi, I'm Alice" → "What's the capital of France?" → "Paris" → "What's my name?" → without resending history, the model has no idea.
- **The context window is the working memory** — the RAM of the LLM; the token is its atomic unit. It holds the system prompt + chat history + current query.
- **Why this bites agents specifically:** an agent makes hundreds of API calls in a single session (LLM ↔ tools ↔ LLM). You *will* exhaust even a very large window, and past that point you get **catastrophic forgetting**.
- **Scale intuition:** ~7,500 tokens ≈ a 5,000-word short story; the *Attention Is All You Need* paper ≈ 10,000 tokens; *The Great Gatsby* ≈ 72,000; ~1M tokens ≈ the complete works of Shakespeare.

### A million tokens is not a magic bullet
- **Lost in the middle:** the model attends to the beginning and end of the context and under-attends the middle.
- **Latency:** attention over 1M tokens is slow; you see longer pauses.
- **Cost:** every resent token is billed on commercial APIs.
- **Reframe:** stop trying to *fit* information and start **managing the signal-to-noise ratio**.

### Memory hierarchy (biological analogy)
| Human | Agent |
|---|---|
| Working memory | Active context window |
| Short-term memory | Recent messages / buffer |
| Long-term memory (unlimited) | Vector databases, external stores |

### Four levels of memory strategy
1. **FIFO / sliding window (buffering).** Keep the last N; drop the rest permanently. Cheap and fast. **Risk: "context cliff"** — critical user facts are lost forever.
2. **Summarization.** In LangChain, `ConversationSummaryBufferMemory(llm=..., max_token_limit=1000)` — keep a running summary, dump the raw history. Preserves narrative flow. Theme for next module: **fidelity over size**.
3. **Hybrid.** User query → summarizer LLM → summary to long-term store; keep recent turns in the buffer; add a retriever to pull relevant history back in.
4. **Agentic memory (memory as a tool).** Memory stops being passive input and becomes something the agent *queries* via the ReAct loop. **The model decides when to remember**, which cuts noise and cost.
   - *Interview-ready answer:* "Summarize and compress important information into a database, then build an agent that actively queries that store alongside its active context."
   - Tooling: LangGraph `StateGraph` + `MemorySaver` checkpointer; MemGPT as an off-the-shelf option (build-vs-buy).

### Chunking strategies (how to slice data for storage)
- **Sentence-based** — most granular (e.g., 10–20 sentence chunks)
- **Recursive / structural** — by header, then paragraph, then subheading
- **Semantic** — embed in latent space and chunk by meaning (most advanced)

### Matching strategy to workload
| Workload | Strategy |
|---|---|
| Short transactional chat | Buffering (sliding window) |
| Long, evolving session | Summarization |
| Knowledge-heavy / FAQ | Vector store (RAG) — covered next session |
| Complex relational reasoning | Knowledge graph memory |

### SQL vs. vector: hard search vs. soft search
- **Hard search** = exact string matching (Ctrl-F, SQL `LIKE`). **Soft search** = semantic similarity.
- **The bottleneck, illustrated:** user asks *"When was the last time I asked for a pizza recipe?"* SQL searches for "pizza" and returns **zero matches** — even though the history contains "homemade ravioli," "dough for calzones," and "cooking Italian food."
- Human memory is semantic; ravioli and dough are *near* pizza in meaning, but SQL cannot see that connection.
- **Fix:** embed the query, do top-k similarity retrieval in a vector store, then let the agent pick the relevant hit.

---

## 6. The Cognitive Triad (the memory types you'll build)

- **Semantic memory — facts.** Who is this person, what do we know about them.
  - *Email agent:* Emily Brown asks for a mockup review → scan the store → she previously asked about dashboard UI changes → respond with that context. For a new sender, semantic memory can even pull public info (LinkedIn, web presence).
- **Episodic memory — experience (few-shot learning from your own past).** What happened last time.
  - *Email agent:* new email from Alice Jones → retrieve: last month's similar email was **ignored** → decide to ignore this one too. Also captures the *vibe* of past exchanges: friend vs. senior manager vs. external company.
- **Procedural memory — instinct and persona, evolved via meta-prompting.** *How* you do things.
  - *Trigger:* user says "stop being so formal" → a prompt-optimizer LLM rewrites the agent's own instructions.
  - Encodes rules like: boss → "Dear John…"; professor → "Dear Professor Amir…"; friend → "Hey John, want to grab coffee?"

### The email agent you'll build
```
Incoming email
   → Triage router (an LLM) picks which memory type(s) to use
   → Action: ignore / notify / respond
   → Response agent draws on semantic + episodic + procedural memory
   → Checks calendar (e.g., is Friday evening free?)
   → Optimizer returns feedback
```
Often all three memory types fire at once on a single email.

---

## 7. Poll Questions and Answers

| Question | Answer |
|---|---|
| Few-shot prompting primarily works by… | Giving a small number of examples in the prompt |
| Main limitation of traditional few-shot prompting for reasoning? | It requires task-specific handcrafted examples |
| Why do transformers struggle with serial reasoning? | They operate at constant depth |
| Virtual depth is achieved by… | Producing long intermediate reasoning sequences |
| What problem does ReAct primarily solve? | Hallucination caused by isolated reasoning |
| Main failure mode of agents that act without reasoning? | Aimless exploration |
| Why do LLMs appear to remember previous messages? | The application resends the conversation history each time |
| Context window is best compared to… | Working memory (RAM) |
| At 1M tokens, what problems remain? | Noise, latency, and reasoning degradation (lost in the middle) |
| Why does SQL fail for reasoning-heavy memory? | It relies on exact string matching, not semantic similarity |
| What do knowledge graphs capture that vector stores miss? | Relationships between entities |
| Which memory type enables few-shot learning from experience? | Episodic memory |

**Side note on temperature** (raised while reviewing a poll distractor): temperature controls output diversity. At 0, the same prompt yields the same response every time; near 1, responses vary. High temperature (~0.9–1.0) is useful when you want to sample several candidates and vote — relevant later for mixture-of-experts.

---

## 8. Q&A

- **Doerte Doepfer — how does "let's think step by step" actually activate dormant reasoning?**
  Purely empirical discovery. The researchers scripted a sweep over many candidate prompts across benchmark datasets and measured accuracy; this phrase simply won. *Why* LLM reasoning works is still an open research question — the "poking the latent space" framing is an intuition, not a mechanism.

- **T — in the zero-shot CoT examples, was reasoning also provided in the prompt?**
  No. The only prompt is "Let's think step by step." The reasoning shown on the slide is the model's *output*, not part of the input. Same for the pond/forest example.

- **Jelani Gould-Bailey — if procedural memory lets the agent rewrite its own system prompt, isn't that a security risk?**
  Yes. Covered in **Module 5** (guardrails). Introduces the tradeoff: **autonomy and speed vs. security and safety** — treated as orthogonal axes. Mitigation is a **security triage agent** that flags items needing human-in-the-loop review.

- **Ganesh Sundaresan — do you choose the memory type up front, and where do episodic/procedural live?**
  You build a **router** that decides at runtime; often all three types are used together. All three are kept in vector databases. Details on vector stores come next session with RAG.

---

## 9. Practical Build Checklist

1. **Always open the agent's prompt with "Let's think step by step."** Zero cost, large effect.
2. **Add 1–2 domain worked examples on top of that.** Zero-shot CoT plus a couple of demonstrations is the strongest combination.
3. **Write down the procedure your organization actually follows** — the checks, in order, that a human expert performs — and encode it as the chain of thought. *(This is explicitly what's expected in the capstone project.)*
4. **Never ship reasoning-only.** Wire the agent to external tools (search, calculator, SQL, APIs, code) so claims can be verified and calculations offloaded.
5. **Never ship acting-only.** Force a Thought step between actions so tool use follows a plan.
6. **Cap loop iterations.** Set a maximum number of tool calls / searches per task.
7. **Engineer memory deliberately.** Pick buffering, summarization, vector store, or knowledge graph based on session shape — don't rely on a big context window.
8. **Use semantic retrieval, not string matching,** for anything memory- or reasoning-heavy.
9. **Use temperature 0** when you need deterministic, repeatable behavior; raise it only when you're sampling candidates to vote on.
10. **Plan for guardrails early** if the agent can modify its own instructions.

---

## Appendix: Transcript Artifacts and Points to Verify

Auto-transcription garbled several names and terms. Corrections and things worth double-checking against the slides:

- **"Ling et Tao, 2017"** → Ling et al., 2017 (the rationale-generation / AQuA math word problem work).
- **"Deep Charcoal"** → almost certainly the **scratchpad** line of work on intermediate computation, not a product named "Deep Charcoal."
- **CoT paper attribution** — the transcript alternates between "Google Research" and "DeepMind." The chain-of-thought prompting paper (*Chain-of-Thought Prompting Elicits Reasoning in Large Language Models*) came out of Google Research/Brain; DeepMind was a separate organization at the time. Worth confirming which attribution the slide uses.
- **"futile / fucial / fuchsia prompting"** → *few-shot prompting* and *few-shot CoT* throughout.
- **"coin philic / Philip"** → the **coin-flip** state-tracking benchmark.
- **"lack of sentences"** → in context this is a *lack of sense-making / synthesis* — the inability to adapt a plan to what an observation means.
- **"conversation summer buffer memory"** → `ConversationSummaryBufferMemory`.
- **"LANGraph / land graph"** → **LangGraph**.
- **"RAC top-case similarities"** → RAG **top-k** similarity retrieval.
- **"context cliffing"** → the context cliff (abrupt loss when the window slides past important content).
- **"neural gap"** → used loosely for the constant-depth limitation on serial reasoning; not a standard term.
- **Temperature range** — stated as 0 to 1. Several APIs allow up to 2; 0–1 is the common practical range but not a hard ceiling.
- **RAM figures** — "500 GB, 1 TB, or 2 TB of RAM" describes disk-scale numbers; typical working memory is far smaller. The analogy (context window ≈ RAM) still holds.
- **Emergence threshold** — the lecture says the effect appears around ~7B parameters, then later says "100 billion parameters are required." These are inconsistent; the slide likely means *reliable* zero-shot CoT emerges at ~100B while weak signal appears earlier.
- **"Gemini 4"** — no such version; likely a mis-transcription of a current Gemini release.
- **Vector stores "based on similarity, not meaning"** — as stated this is backwards relative to the rest of the lecture. Embedding similarity is precisely what captures *meaning*, which is the whole argument against SQL string matching. Treat as a misspeak.
- **1M tokens ≈ all of Shakespeare** — a reasonable order-of-magnitude claim; the complete works run somewhat above 1M tokens.
