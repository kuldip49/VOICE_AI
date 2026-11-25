# AI concepts, explained with this project

Each section: simple idea first, then the technical term, then where it lives in SalesPilot.

## Artificial intelligence (AI)
Software that does tasks we normally think need human judgement: understanding language, deciding what to do next. SalesPilot mixes two kinds:
- **Rule-based AI**: hand-written rules (e.g. "if the message contains *too expensive*, it is a price objection"). Predictable, cheap, testable.
- **Machine-learned AI**: models trained on data (the LLM, Chrome's speech recogniser). Flexible, but can be wrong in surprising ways.
Interview line: *"I used ML where flexibility matters (language understanding and generation) and rules where correctness matters (bookings, scoring)."*

## Large Language Models (LLMs)
A neural network trained to predict the next word on huge amounts of text. Given instructions + context, it writes fluent text. Examples: Gemini, Llama (via Ollama).
- **Prompt**: the text we send. Ours = system instructions + retrieved documents + known customer facts + the last 8 messages (`orchestrator.py → _llm_answer`).
- **Hallucination**: the model states something false confidently. We reduce it by (1) giving it only retrieved facts, (2) telling it to say "not in the knowledge base", (3) **not calling it at all** when retrieval found nothing, (4) keeping booking text out of its hands.
- **Temperature**: randomness. We use 0.3 for consistent answers.
- **Tokens / context window**: models read a limited amount of text, priced per token. That is why we send only recent turns plus a summary.

## Speech-to-Text (STT)
Turns audio into text. We use the browser's **Web Speech API** (`SpeechRecognition`). Chrome sends audio to Google's service and returns text with *interim* (partial) and *final* results. Language codes `en-IN`, `hi-IN`. Limits: Chrome/Edge only, needs internet, accuracy drops with noise and accents. Alternatives: OpenAI Whisper (open source, can run locally), Vosk, Deepgram, Azure Speech.
Code: `frontend/src/hooks/useVoice.ts → listen()`.

## Text-to-Speech (TTS)
Turns text into audio. We use `speechSynthesis` with a voice that matches the reply language. Hindi needs a Hindi voice installed (Edge on Windows has them). We strip bullets/markdown so it sounds natural. Alternatives: Piper, Coqui (open source), ElevenLabs, Azure Neural TTS.

## Natural Language Processing (NLP)
Getting structure out of human language. Our NLP pieces:
- **Language detection**: Devanagari characters or Hinglish words → Hindi.
- **Information extraction**: regular expressions pull name, email, phone, budget ("20k", "1.5 lakh", "20 हज़ार"), timeline (`services/extraction.py`).
- **Intent detection**: is this a question, a booking request, a slot choice, a yes/no? (`orchestrator.py → _intents`).

## Retrieval-Augmented Generation (RAG)
Simple idea: *before answering, look it up in the company's documents, then answer using what you found.*
1. **Ingest**: upload PDF/TXT → extract text (`pypdf`).
2. **Chunk**: split into sections (`## Heading`), max ~1200 characters. One course = one chunk, so a price is never separated from its course name.
3. **Index**: BM25 keyword statistics (and embeddings if available).
4. **Retrieve**: score every chunk for the question, keep the best 1-3.
5. **Augment**: paste those chunks into the prompt as "the only allowed source of facts".
6. **Generate**: LLM writes the answer, or demo mode quotes the lines.
7. **Cite**: chunks are returned as `sources` and shown as chips under the answer.
**Not-found guard**: if the best score is below 3.0, or the question has a specific word that appears nowhere in the documents (e.g. "blockchain") and only generic words match ("course", "offer"), we answer "not in our knowledge base". Test it in Knowledge base → Test retrieval.

## Embeddings
A list of numbers (a vector) that represents meaning. Sentences with similar meaning get vectors pointing in similar directions, even with different words ("fees" vs "cost"). Similarity is measured with **cosine similarity**. In SalesPilot, if a Gemini key is set, each chunk gets an embedding and retrieval blends cosine similarity with BM25 (**hybrid search**). Without a key we use BM25 plus a small synonym/Hindi dictionary (`rag.py → SYNONYMS`).

## Vector search
Finding the vectors closest to the question's vector. For thousands of chunks you use an index (HNSW) in a vector database (pgvector, Qdrant, FAISS). Our MVP compares against every chunk because there are only ~25.

**BM25** (what we use by default): a classic ranking formula. A chunk scores higher when it contains the query words often (term frequency), when those words are rare across all chunks (inverse document frequency, so "refund" counts more than "course"), and it normalises for chunk length.

## Contextual memory
- **Short-term (session) memory**: the conversation's messages + `conversation.state` (offered slots, pending booking, what we just asked). It lets "2" mean "slot 2" and a bare "Rahul" mean a name.
- **Long-term memory**: `customer_memories` key/value facts that survive across conversations. Start a new conversation with the same `customer_id` and Nova greets them by name.
- **Context window strategy**: only the last 8 messages go to the LLM; older ones are compressed into `memory_summary` (facts + topics). Prevents cost and length growing forever.
- **Contextual retrieval**: "What's the price?" has no course name, so the remembered interest is appended to the search query.

## AI agents
A program that decides *which actions to take* toward a goal, uses tools, observes results, then responds. Ours: goal = help the customer and qualify the lead; tools = 10 functions; planner = intent rules; memory = DB. It is an agent, not a chatbot, because it acts (books, updates CRM, scores) and every action is logged.

## Function calling / tool use
Letting an AI call code with structured arguments. In SalesPilot each tool has a Pydantic schema (like a JSON Schema). `execute_tool()` validates arguments, checks the tool is permitted, runs it, and logs input/output/duration. Today the planner picks tools; with Gemini function calling the model could pick them, and the same validation layer would still protect the database.

## Sentiment analysis
Classifying feelings in text: positive, neutral, negative, frustrated, interested, hesitant. Ours is lexicon-based (lists of cue phrases in English/Hindi/Hinglish), with a priority order and a confidence that drops when signals are mixed. It also detects **objections** (price, time, uncertainty, trust, authority) and suggests an action. Sentiment is not intent: "Thanks, but I'm not interested" is polite yet negative for sales.

## Lead scoring
Turning conversation facts into a priority number. Ours is a transparent points system (weights editable in Settings):

| Criterion | Max | How points are earned |
|---|---|---|
| Purchase intent | 30 | high (enrol/book) 100%, medium (price/batch questions) 60%, low 30% |
| Budget fit | 20 | budget ÷ KB price: ≥100% full, ≥70% 60%, ≥40% 30%, else 10% |
| Urgency | 20 | immediately 100%, within a month 85%, 1-3 months 50%, later 20% |
| Product interest | 15 | a specific course identified |
| Readiness | 15 | contact shared 50% + appointment booked 50% |

HOT ≥ 70, WARM ≥ 40, else COLD. Unknown facts score 0, never guessed. Each point has a stored reason, e.g. "Budget ₹20,000 vs price ₹45,000 (44%): +6/20".

## API communication
The browser and backend talk over **HTTP** using **REST** conventions (resources + verbs: `POST /api/conversations`, `GET /api/leads`) with **JSON** bodies. FastAPI validates every request with Pydantic and returns 4xx codes for bad input (422 invalid, 404 not found, 409 conflict like a taken slot, 429 rate limited). The LLM is called the same way: an HTTPS POST to Gemini or to Ollama on localhost.
