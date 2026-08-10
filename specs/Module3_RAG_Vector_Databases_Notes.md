# Module 3 — RAG, Agents & Vector Databases
**Instructor:** Prof. Amir Barati Farimani
**Chat support:** Hitesh K, Karthik Venkatachalam, Gerardo Bodegas Martinez (peer answers)
**Session length:** ~2h04m, with ~30 minutes of Q&A at the end
**Sources:** lecture transcript + Zoom chat log (the chat runs a parallel, unusually substantive Q&A thread)

The arc: why LLMs need external knowledge → build a naive RAG by hand → why naive RAG breaks → advanced RAG → modular/agentic RAG → RAG vs. fine-tuning.

---

## 1. The Problem RAG Solves

**Frozen parameters vs. dynamic data.** An LLM's weights are fixed at the end of training. Its knowledge is only as fresh as that moment — it has no idea what happened this morning, what a stock is trading at, or what was announced an hour ago.

Three specific failures of parametric-only knowledge:

| Failure | What it means |
|---|---|
| **Hallucination** | With no access to factual data, the model falls back on probabilistic guessing |
| **Outdated knowledge** | Stock prices, news, policy changes — none of it reaches a frozen model |
| **Opacity** | No source attribution, so nothing can be fact-checked |

**RAG = retrieval-augmented generation:** synergistically merging the LLM's intrinsic parametric knowledge with external, dynamic knowledge stores.

### The open-book exam analogy (the framing worth keeping)

- **Closed-book exam = standard LLM.** You half-remember the equation. Was it ∂u/∂t or ∂u/∂x? You write down something plausible and get it wrong. **That's hallucination.**
- **Open-book exam = RAG.** You still need your brain to reason through the problem, but you can turn to page 25 of the heat transfer book and copy the equation exactly.

Note what the analogy preserves: open-book is *harder*, not easier. You still have to find the right page in 300 dense pages. Retrieval quality is the whole game.

### Opening polls

| Question | Answer |
|---|---|
| Biggest weakness of an LLM-only system in production? | Hallucination and outdated knowledge |
| Why are LLMs said to have static parametric memory? | Their knowledge is fixed after training |
| What does hallucination stem from? | Probabilistic next-token prediction |

> **Chat clarification worth noting** (Tochi E. asked, Karthik answered): RAG *reduces* hallucination by grounding generation in retrieved evidence, but it does not remove the underlying mechanism. The poll asks about the **root cause**, which is still next-token prediction. RAG constrains it; it doesn't replace it.

---

## 2. How RAG Works — The Four Steps

**1. Chunking.** A 10-page PDF embedded as one vector mixes too many concepts together. Split it into paragraphs or smaller pieces so each vector represents one coherent idea.

**2. Embedding.** An embedding model converts each text chunk into a numerical vector that captures semantic meaning. *Why numbers?* Because comparing meaning directly is intractable — comparing numbers is easy.

**3. Retrieval via cosine similarity.** The user's prompt is embedded the same way. Then you find the stored vectors closest in angle to the query vector:

```
cos θ = (A · B) / (‖A‖ ‖B‖)
```

Dot product over the product of magnitudes. **θ → 0 means maximum similarity.** Rank the results and return the top *n* (a hyperparameter — 3 is typical).

**4. Augmentation and generation.** The retrieved *text* (not the vectors) is injected into the prompt alongside the query, with an instruction like *"use only the following pieces of context to answer the question; don't make up any new information."* The LLM then **synthesizes** — it wraps the raw fact in fluent language and cites the source.

> **Important chat clarification** (Joseph Antonysamy asked; Karthik and Gerardo both answered): **only the text chunks go to the LLM, never the embedding vectors.** The vectors are a *search key* used to find the right text. Once retrieval is done, the LLM reads plain text.

### Polls on the mechanics

| Question | Answer |
|---|---|
| Purpose of embedding in RAG? | Convert text into numerical values |
| What is chunking in the indexing phase? | Splitting documents into smaller pieces |
| What does cosine similarity measure? | Distance between semantic vectors |
| Why inject retrieved chunks into the prompt? | To ground the model's response in retrieved facts |
| In RAG, the LLM acts primarily as… | A synthesizer of retrieved knowledge |
| Main benefit of RAG over retraining? | Instant updates without retraining |
| Why does RAG improve traceability? | It cites retrieved source documents |
| RAG combines which two kinds of knowledge? | Parametric and non-parametric |

---

## 3. The Hands-On Build (the cat-facts demo)

The tutorial builds a working naive RAG in about 30 lines:

1. **Install** — `pip install ollama`; two small models from Hugging Face (a generator and an embedding model, `bge-base-en`), both runnable locally
2. **Load** — open `cat-facts.txt`, read it into memory
3. **Chunk** — split the text into pieces, build a list of `(chunk, vector)` tuples
4. **Embed** — the embedding model converts each chunk to a numeric vector
5. **Query** — *"Tell me about cat speed."* The question is embedded the same way
6. **Retrieve** — write `cosine_similarity(a, b)` by hand: dot product over norms. Rank, keep top 3. The best match scored **0.82**
7. **Generate** — prompt the chat model with *"You are a helpful chatbot. Use only the following piece of context to answer. Don't make up any new information,"* plus the retrieved chunk

**Result:** *"According to the given context, cats can travel at approximately 31 miles per hour (50 km/h) over short distances."* Note the model **wrapped** the fact rather than echoing it — that's synthesis.

**This is deliberately not production-grade.** It exists to make the pipeline concrete.

---

## 4. Why Naive RAG Breaks

Three failure modes, each mapping to a stage:

- **Retrieval failure** — low precision/recall; the crucial chunk is never returned
- **Generation failure** — the model ignores the instruction and uses parametric knowledge anyway; toxicity and bias leak through
- **Augmentation failure** — disjointed output, lost-in-the-middle when too much context is stuffed in

And three specific traps:

**Multi-topic confusion.** Ask about cat speed and Schrödinger's cat in the same breath, and similarity search can't cleanly separate quantum mechanics from feline biomechanics.

**The similarity trap.** High cosine similarity with wrong meaning — *blood bank* and *savings bank* share vocabulary but not semantics. **Vocabulary overlap is not contextual relevance.**

**Scalability.** In-memory vector storage doesn't survive scale or restarts. This is why vector databases are becoming a serious business — the professor's prediction is that continuously-refreshed vector stores of world knowledge become a major product category.

### Polls on limitations

| Question | Answer |
|---|---|
| Key weakness of similarity-only retrieval? | It may miss multi-topic context |
| Purpose of a re-ranking model? | Improve ordering of retrieved chunks |
| Why is storing vectors in memory problematic at scale? | It limits scalability and persistence |
| Why is retrieval quality central to RAG performance? | **The generator cannot correct bad retrieval** |

> That last one is the load-bearing insight. You told the generator to use only the retrieved context. So if retrieval returns garbage, the generator faithfully wraps garbage in fluent prose and hands it to your customer.

---

## 5. Advanced RAG — Pre- and Post-Retrieval

### Pre-retrieval (better indexing and better queries)

- **Sliding-window chunking** — overlap consecutive chunks so semantics aren't severed at a boundary. Chunk 1 covers tokens 0–1000, chunk 2 starts at 800. **Typical overlap: 20%.**
- **Fine-grained and hierarchical segmentation** — parent chunks with child chunks beneath them (e.g. "cat physiology" as parent, with body/dimensions, dynamics/speed, breed/color as children). Retrieve at multiple levels and re-rank across them.
- **Query optimization / HyDE** — a second LLM rewrites the user's vague query into something retrievable. The worked example: *"Tell me why you didn't approve my loan"* becomes *"Can you tell me the reasons and justifications behind why my loan application was not approved, with documentation and citation?"*
- **Stronger or domain-fine-tuned embedding models** — a bank should fine-tune embeddings on *mortgage, loan, credit history, transaction* rather than use a general model that knows about cat speed. This is what companies actually do.

### Post-retrieval

- **Re-ranking** — reorder the retrieved chunks by relevance before generation
- **Context compression** — strip semantically irrelevant tokens to cut noise
- **Recursive retrieval** — loop retrieval and generation multiple times

### Polls

| Question | Answer |
|---|---|
| How is HyDE used? | Rewrite or expand queries before retrieval |
| What does context compression aim to achieve? | Remove semantically irrelevant tokens |

### How re-ranking actually works (Sarita's question)
With HyDE you generate several rewritten queries. Each query returns its own top-3 by similarity — so three queries give nine scored candidates. Re-ranking merges and re-sorts all nine, and a result from query #3 may well outrank the second-best result from query #1.

---

## 6. Modular RAG — the Production Pattern

The motivating failure: *"Analyze NVIDIA versus Apple financial performance."* Naive RAG retrieves NVIDIA's annual report section 7, finds nothing comparable for Apple, and produces an answer that can't actually compare.

Modular RAG adds orchestration components around the retrieve-then-generate core:

- **Routing** — a router inspects the query and decides the path: simple lookup, multi-hop reasoning chain, or a different LLM entirely
- **Memory**
- **Verification / judges** — an LLM reads the retrieved results and asks whether they're logical. If the retrieval says a cat runs 200 mph, the judge rejects it and sends the query back to be rewritten
- **Fusion / ensemble** — run several generators, then have another LLM fuse the outputs
- **Prediction and demonstration modules**

**The pattern:** retrieve → read → judge → (if unsatisfactory) rewrite → retrieve again. A loop, not a pipeline. This is the foundation of **agentic RAG**.

### Judges as guardrails
Routers double as a safety layer. A query like *"Is it good for my health to eat glass powder daily?"* gets stopped at the router, not answered. In safety-critical domains (medical, autonomous vehicles), these judges are themselves fine-tuned LLMs with domain knowledge, checking toxicity and confidence at each step.

**Human-in-the-loop triage** (previewed for Module 6): confidence is scored and answers are triaged three ways — high confidence passes automatically for speed, a gray zone draws on past experience, and low confidence escalates to a human expert via a GUI showing the LLM's reasoning and its stated uncertainty, with approve / override / escalate options.

---

## 7. RAG vs. Fine-Tuning

| | RAG | Fine-tuning |
|---|---|---|
| **Best for** | Dynamic, evolving data | Tone, style, vocabulary, format, instruction-following |
| **Solves** | Hallucination, factuality, freshness | Behavioral adaptation |
| **Transparency** | High — cites sources | Low — knowledge is internal |
| **Update cost** | Instant | Requires retraining |

**The quad chart:**
- Low external knowledge need + low adaptation need → **prompt engineering is enough**
- High adaptation + slow-changing data → **fine-tuning**
- Fast-changing data → **RAG**
- Both → **hybrid**, which is what most organizations actually do

**Verdict: not mutually exclusive.** Use RAG for knowledge and fine-tuning for behavior. And you can fine-tune two different things — the **embedding model** (better retrieval in your domain) and the **generator** (better voice and format).

> Asked directly whether you could skip RAG and fine-tune on your Q&A instead (Sarita), the answer was no: with RAG, new data goes into the vector store and is immediately queryable. With fine-tuning, every new fact means retraining.

---

## 8. Infrastructure and Ecosystem

**The stack:** Python environment → a local model server → your document directory → GPU → vector store → UI.

| Layer | Tools named |
|---|---|
| Orchestration | LangChain, LlamaIndex, DSPy, MCP |
| Embedding | Sentence Transformers, BGE models |
| Vector stores | FAISS, Pinecone, Chroma, Weaviate, Qdrant, pgvector |
| Evaluation | RAGAS, ARES, TruLens |
| Specialized platforms | Flowise AI, Haystack |
| UI | Streamlit or React |

**Loading heterogeneous documents:** `SimpleDirectoryReader` ingests PDFs, PPTX, EPUB, MP3, video — because a bank has customer-service call recordings and branch footage, not just PDFs.

**Key settings:** chunk size ~1024 tokens (a common default, not a magic number), 20% overlap, **temperature 0** for deterministic output.

**Multimodal RAG** models mentioned for later exploration: RA-CM3 (text+image retrieval and generation), BLIP-2 (zero-shot image-to-text), plus audio/video and code-specific retrieval models.

### The privacy argument (the professor's core recommendation)
> Build a vector database of your organization's proprietary documents, keep it on your own infrastructure, and use the LLM purely as a wrapper that generates the response. Your data stays confidential; the model never needs to see it in training.

**Counterpoint raised in chat by Gerardo** and worth carrying into any design: a vector database is **a second copy of your data**. That copy has its own access control, retention, and compliance obligations. RAG doesn't eliminate a security surface — it adds one.

---

## 9. Q&A — Live

**Mazen Skaf — if context windows had no limits, would we still need RAG?**
Yes. Context window is about how much text fits in one session; RAG is about **freshness and factuality**. And in an agentic system running 24/7, you'll exhaust any window regardless, because it's machine-driven, not a human uploading ten PDFs.
*(Note: this sits in tension with a bullet on his own future-directions slide — see appendix.)*

**Denis Sheridan — telling the model "don't hallucinate" implies it knows when it's hallucinating. Does it?**
**No.** The model has no self-awareness of hallucinating; it's still just next-token prediction. What the instruction does is **block the model from entering generative mode at all** for the factual content — it's told to use only the supplied text and wrap it. The model might have produced a correct answer on its own, but you don't take that risk.

**Denis follow-up — where do citations come from?**
Store the tuple as `(chunk, vector, source_id)`. On retrieval, you go vector → chunk → source ID → citation. **Metadata** (publication date, document type, origin — Elsevier paper vs. NVIDIA Q3 report) lives in a relational store keyed by that source ID. This is exactly what the citation icons in ChatGPT are doing.

**T — how do you actually stop the model using its parametric knowledge?**
You largely can't with a single instruction. Naive RAG fails at this; the model can effectively jailbreak itself. Production systems use **multiple judges and routers**, covered in Module 6. *(Gerardo's chat answer was blunter: there's no way to fully block internal knowledge, and models sometimes ignore provided context in favor of training. Prompt instructions help but guarantee nothing.)*

**Shawn Cunningham — open-source vector DBs for a fully offline, low-bandwidth system?**
Postgres + pgvector is a good choice, and gives relational storage in the same system. **Juan Hernandez recommended Qdrant** (written in Rust, fast). Athul added Chroma for small-scale work.

**dselvaraj — is there an optimal chunk size?**
It depends on document type, embedding model, and retrieval task. In practice ~1000–1024 tokens with 20% overlap is a common working default. For video, chunk by frames — roughly one second at a time.

**Dimple — does similarity comparison work for numbers/math?**
It works *better* for numbers, because the metric is numeric to begin with. The lossy step is converting language to numbers. For pure numeric comparison, cosine is one option among several (Manhattan, Euclidean); cosine tends to work best in learned latent spaces.

**Athul A T — should chunks respect paragraph boundaries rather than cutting at 1024 tokens?**
Yes, and the frameworks handle this — LangChain and similar will avoid splitting mid-sentence. Beyond that, **semantic and hierarchical chunking** (parent/child) is the more advanced approach, retrieving at multiple granularities and re-ranking across them.

**T — do systems ever run the LLM first and then use RAG to validate?**
Frontier models now all have some form of internal RAG — the citation icons, Google's AI search results. But **a vanilla LLM cannot cite anything**: it's next-token prediction, so there's no mechanism by which a citation could be produced. Any citation you see is retrieval bolted on.

---

## 10. Q&A — Chat Only

**Shankar — can you always see the augmented prompt sent to the LLM?**
If you build the pipeline yourself, yes — log it for traceability and debugging. Whether a third-party tool exposes it depends on its design.

**Shankar — is each chunk a vector, and is the prompt also one vector?**
Yes to both. Each chunk (paragraph, section, sometimes a page) becomes one embedding; the query becomes one embedding; similarity is computed between them. *(His follow-up — does an arbitrarily long prompt collapse to a single vector? — went unanswered and is worth investigating.)*

**Tochi — must chunking tokenize consistently with the model's dictionary?**
Ideally yes; embedding and chunking must be consistent between query and stored documents or retrieval degrades. *(Viral Kadakia sharpened the question — consistency between query and stored embeddings, or between embeddings and the generator's vocabulary? Not resolved in the chat.)*

**Andrew Kopshin — how are vector values assigned? Is it ID tagging?**
No. Vectors aren't IDs or tags — they're numeric representations of meaning produced by an embedding model. Similar chunks land near each other, which is why semantic search works.

**dselvaraj — do different embedding models produce different vectors?**
Yes, for the same text. *(Which is why you cannot mix embedding models between indexing and querying.)*

**Jacques Troussard — is RAG only about accuracy?**
No. It also supports **guardrails and policy checks** — retrieve approved policies, safety rules, or compliance documents before generating. And it supplies proprietary knowledge that could never have been in training.

**Tochi — is retrieved context used exclusively, or alongside parametric knowledge?**
Alongside, in most systems. The LLM still has its training knowledge and may also use other tools. You can instruct it to rely only on retrieved chunks, but that's a request, not a guarantee.

**Deepa — for daily-updated news, rebuild the vector DB every day?**
No — add, update, or re-embed only the new or changed content.

**Viral Kadakia / Deepa — do user prompts and retrieved context fine-tune the model?**
No. Both are inference-time only. Remove the RAG context and the model falls back to its original parametric knowledge; nothing was learned permanently.

**Yimeng Liu — is LlamaIndex a model?**
No. It's a framework for connecting data sources, building indexes, and running retrieval.

**Yimeng Liu — is sliding window something we set ourselves?**
Yes — window size and overlap are *your* chunking parameters. The model's context window limit is fixed by the model. Two different things.

**Doerte Doepfer — what does "hybrid" mean here?**
Combining RAG (for current external knowledge) with fine-tuning (for behavior, style, domain expertise).

**Shankar — what's a knowledge graph, versus a vector DB?**
A knowledge graph stores **entities and relationships** (Customer → bought → Product); a vector database stores **embeddings for similarity search**. Graphs are about connections; vectors are about similarity. Graphs are built by extracting entities and relations from documents.

**Joseph Antonysamy — why RAG structured data when you have DB tools? Isn't MCP the way to query SQL?**
Good exchange with no single answer. Points made: RAG isn't limited to vector stores — you can implement retrieval over SQL (text-to-SQL as the retrieval layer, results passed as context). Gerardo's distinction is the clean one: **MCP is a protocol for exposing a resource to any LLM; RAG is a pattern you implement for a specific system.** They operate at different levels.

**Sirisha — does HyDE ship in frontier models by default?**
Unresolved. The interesting use is in your own pipeline, enriching the user's prompt before searching your vector store.

**Yimeng Liu — are lower embedding dimensions beneficial?**
A real trade-off: smaller vectors mean less storage and faster retrieval, at some cost in semantic detail. Achieved by choosing a lower-dimension embedding model or applying dimensionality reduction.

**Unanswered in the session** — Anthony Wang and Sirisha both asked about **Agentic RAG** specifically (is it a fourth category beyond naive/advanced/modular?). Never addressed directly. The closing slides treat agentic RAG as the direction modular RAG points toward rather than a distinct tier. Worth raising in a lab.

**Gerardo shared the HyDE paper:** arXiv 2212.10496.

---

## 11. Closing Framing

RAG's active research frontier has moved from *can we do RAG* to *can we do RAG in production at scale*. Open questions raised: robustness against **poisoned retrieval** (misinformation inside your chunks), whether scaling laws apply to RAG, and general production readiness.

The professor's long view: today's operating systems — the thing managing your Word, Excel, and email — get displaced by **LLMs as the operating system**, which requires both ReAct (reasoning and acting through tools) and RAG (grounding in fresh data) working together.

---

## 12. Appendix: Errors, Garbles, and Things to Verify

### Substantive corrections

- **Vector database vendor attributions are wrong.** The lecture states "Pinecone is from Amazon" and "ChromaDB is from Google." **Pinecone is an independent company; Chroma is an independent open-source project.** FAISS from Meta is correct. Don't repeat these attributions in a writeup.
- **Ollama is not from Meta.** The transcript describes the local-model tool as coming "from Llama, from Meta." **Ollama** is an independent tool for running models locally; **Llama** is Meta's model family. Two different things with confusingly similar names. The demo uses Ollama to serve a Llama-family model, which is probably where the conflation started.
- **"RAG is reasoning and acting."** Near the close: *"RAG is reasoning and acting, connecting to the tools… and RAG is connecting to the vector databases."* The first one is **ReAct**. The point being made — that agentic operating systems need both ReAct and RAG — is right; the naming collapsed.
- **HyDE is described imprecisely.** The lecture presents it as query rewriting/expansion, and the poll answer follows that. **HyDE (Hypothetical Document Embeddings) actually has the LLM generate a hypothetical *answer document* to the query, then embeds that document for retrieval** — the insight being that a fake answer sits closer in embedding space to real answers than the question does. Query rewriting is related but not the same technique. Check the paper (arXiv 2212.10496) before describing it.
- **The in-memory scalability explanation drifts.** The stated reason — "the vectors become so close to each other" and "as you increase model size you must increase embedding space" — isn't the issue. In-memory storage fails at scale because of **RAM limits and lack of persistence** (data vanishes on restart, can't be shared across processes). The poll's own answer, "limits scalability and persistence," is correct; the spoken explanation isn't.
- **Cosine similarity measures angle, not distance.** The poll answer says "distance between semantic vectors," which is loose. Cosine *similarity* measures orientation; cosine *distance* = 1 − similarity. The formula given in the lecture is correct.
- **"Negative and imperative words like don't and stop are highly effective"** — offered in answer to Denis's question, with no source. Much prompt-engineering guidance suggests the opposite (positive framing outperforms negative). Treat as the instructor's experience, not established practice.
- **"200,000 tokens will kill RAG"** appears on the future-directions slide, but the Q&A answer to Mazen argues RAG is needed regardless of context length. These sit in tension. The genuine debate — long-context vs. retrieval — is live and unsettled; note both positions rather than picking one.
- **"30 frames = 1 second"** for video chunking — true at 30fps, but 24, 25, and 60fps are all common.
- **"100 trillion parameters"** for frontier models is repeated from Module 1. Still undisclosed and unverified.

### Transcription garbles

- "Heidi" / "high D" → **HyDE**
- "Olomo" / "Olama" / "LOMO" → **Ollama** (the tool) or **Llama** (the model), depending on context
- "Lomo Index" / "LOMA Index" → **LlamaIndex**; "Lang Chain" / "LanChange" → **LangChain**; "DSPI" → **DSPy**
- "BG-BaseEN" → **bge-base-en** (BAAI General Embedding)
- "quadrant" / "QB Rant" → **Qdrant**; "PG Vector" → **pgvector**
- "VV8, which is Verba" → **Weaviate** (Verba is Weaviate's open-source RAG app); "Kantra, Cohere, Coral" → garbled, likely **Cohere** products, which are not vector databases
- "FAS" → **FAISS**; "ChromeDB" → **Chroma / ChromaDB**
- "RAGS, ARIS and TrueLens" → **RAGAS, ARES, TruLens**
- "RACM3" → **RA-CM3**; "BILEP2" / "Believe 2" → **BLIP-2**; "RBPS" → unclear, likely a code-retrieval model
- "Sheridan cat" / "Sheridania CAT" → **Schrödinger's cat**
- "10 to 24" → **1024** (tokens, chunk size)
- "loss in the middle" → **lost in the middle**
- "intoxication" → **toxicity**
- "Kelod" / "Cloud" → **Claude**
- "GOI" → **GUI**
