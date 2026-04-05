# 🤖 LLM-Powered Test Data Generator

> **Bulk-generate structured, locale-aware chatbot test scenarios in seconds** — using Groq's Llama 3 LLM. Outputs production-ready JSON for automation, regression suites, and manual QA preparation.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-Llama3-F55036?style=flat)
![JSON](https://img.shields.io/badge/Output-JSON%20%2F%20CSV-lightgrey?style=flat)
![Multilingual](https://img.shields.io/badge/Locales-Multilingual-blue?style=flat)

---

## 🧠 Problem → Solution

| Problem | Solution |
|--------|---------|
| Creating hundreds of chatbot test cases manually is slow & inconsistent | LLM generates high-volume, diverse scenarios from seed descriptions |
| Test data lacks realistic multilingual variation | Locale flags (`ta-IN`, `hi-IN`, `en-US` etc.) produce native-language test messages |
| Rate-limit failures when calling LLM APIs at scale | Built-in retry logic (`tenacity`) + configurable throttle delay |

---

## ⚙️ Tech Stack

| Tool | Purpose |
|------|---------|
| **Python 3.11+** | Core language |
| **Groq API** | Ultra-fast LLM inference (Llama 3.1 8B) |
| **tenacity** | Automatic retry with exponential backoff |
| **python-dotenv** | Secure API key management |
| **JSON / CSV** | Structured output formats |

---

## 🚀 Setup & Run

### 1. Clone the repository
```bash
git clone https://github.com/QualitySentinelMaestro/LLL-TestData-Generator.git
cd LLL-TestData-Generator
```

### 2. Create a virtual environment & install dependencies
```bash
python -m venv .venv
source .venv/bin/activate
pip install requests python-dotenv tenacity
```

### 3. Configure environment variables
```bash
cp .env.example .env
# Edit .env and fill in your keys
```

`.env.example`:
```
GROQ_API_KEY=your_groq_api_key_here
GROQ_API_URL=https://api.groq.com/openai/v1/chat/completions
GROQ_MODEL=llama-3.1-8b-instant
```

### 4. Run bulk generation

**Locale-aware generation (e.g., Tamil):**
```bash
python GenerateLocaleTestData.py --locale ta-IN --per-seed 5 --kb 1
```

**Dry run (preview prompt, no API call):**
```bash
python GenerateLocaleTestData.py --locale hi-IN --per-seed 1 --dry-run
```

**Bulk run with custom seeds:**
```bash
python runbulk.py
```

---

## 📤 Sample Output

**Input seed:** `"FAQ about warranty + order lookup + long complaint"`

**Generated Output (`generated_messages.json`):**
```json
[
  {
    "id": "uuid-123",
    "locale": "ta-IN",
    "message": "என் ஆர்டர் எங்கே இருக்கிறது? கடந்த 10 நாட்களாக பதில் இல்லை...",
    "seed": "FAQ about warranty + order lookup + long complaint"
  },
  ...
]
```

---

## 🛠️ Configuration (`runbulk.py`)

```python
PER_SEED = 25      # messages per seed → total = len(seeds) × PER_SEED
KB = 1             # ~1 KB per message (controls length)
THROTTLE = 3.0     # seconds between requests (avoids rate limits)
OUT = "generated_messages.json"
```

---

## 🗂️ Supported Locales

| Code | Language |
|------|---------|
| `en-US` | English (US) |
| `en-GB` | English (UK) |
| `ta-IN` | Tamil |
| `hi-IN` | Hindi |
| `it-IT` | Italian |
| `es-ES` | Spanish |

> Extend easily by adding entries to `LOCALE_TO_LANGUAGE` in `GenerateLocaleTestData.py`

---

## 📁 Project Structure

```
LLL-TestData-Generator/
├── GenerateLocaleTestData.py   # Locale-aware bulk generator with retry logic
├── TestcaseTokens.py           # Core generation utilities & rate-safe runner
├── runbulk.py                  # Quick-run script with configurable seeds
├── .env.example                # Template for environment variables
├── .gitignore
└── README.md
```

---

## 🔮 Roadmap

- [ ] CSV export support
- [ ] Web UI to select locale, seeds, and volume without code
- [ ] Support for additional LLM providers (OpenAI, Anthropic)
- [ ] Integration with Botium / Dialogflow test runners

---

## 🪪 License

MIT License — free to use and extend.
