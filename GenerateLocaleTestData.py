#!/usr/bin/env python3
"""
groq_bulk_generate_locale.py
Generate bulk visitor messages from Groq in a specific locale/language.

Usage examples:
  # generate 5 messages per seed in Tamil
  python groq_bulk_generate_locale.py --locale ta-IN --per-seed 5 --kb 1

  # test prompt only (no API call)
  python groq_bulk_generate_locale.py --locale hi-IN --per-seed 1 --dry-run
"""
import os, json, time, argparse, uuid, re
import requests
from dotenv import load_dotenv
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

# load .env
load_dotenv()

# config
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
print("Key loaded:", bool(GROQ_API_KEY))

GROQ_API_URL = os.getenv("GROQ_API_URL")
print("Key loaded:", bool(GROQ_API_URL))

DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

if not GROQ_API_KEY:
    raise EnvironmentError("GROQ_API_KEY not found. Put it in .env or export it in the environment.")

HEADERS = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}

# map locale -> human language instruction (extend as needed)
LOCALE_TO_LANGUAGE = {
    "en-US": "English (United States)",
    "en-GB": "English (UK)",
    "it-IT": "Italian",
    "es-ES": "Spanish",
    # add more locales as required
}

DEFAULT_SEEDS = [
    "FAQ about warranty + order lookup + long complaint",
    "Order tracking long form and address correction",
    "Returns policy + API error + JSON payload included",
    "Product recommendation + warranty transfer request"
]

def _tokens_for_kb(kb):
    try:
        return max(32, int(kb * 1024 // 4))
    except:
        return 256

@retry(wait=wait_exponential(multiplier=1, min=1, max=10), stop=stop_after_attempt(3),
       retry=retry_if_exception_type((requests.exceptions.RequestException,)))
def call_groq(messages, model=DEFAULT_MODEL, max_tokens=256, timeout=120):
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens}
    r = requests.post(GROQ_API_URL, json=payload, headers=HEADERS, timeout=timeout)
    if not (200 <= r.status_code < 300):
        # surface concise debug info (do not leak API key)
        print("GROQ error:", r.status_code, r.text[:1000])
        r.raise_for_status()
    return r.json()

def build_prompt(seed: str, locale: str, language_label: str, kb: int):
    """
    Returns a messages array suitable for Groq chat completion.
    """
    # force the LLM to produce outputs in the requested language ONLY
    instr = (
        f"Generate a single visitor message of approximately ~{kb} KB intended to test a customer support chatbot. "
        f"The message must reflect the scenario: {seed}. "
        f"Include natural user content typical for customers: short paragraphs, multi-part questions, emotional phrases, emojis, "
        "repeated characters, a short code snippet (optional), and a small JSON block (optional). "
        f"**IMPORTANT**: Return the message ONLY in {language_label} (do not mix in other languages). "
        "Return the visitor message only — no commentary, no numbered explanation. "
    )
    # include locale token to help tracing later
    trace = f"[[LOCALE:{locale}]] [[TRACE:{uuid.uuid4().hex[:8]}]]"
    user_prompt = instr + "\nSeed: " + seed + "\n\n" + trace
    return [
        {"role": "system", "content": "You are a test-case generator for QA automation."},
        {"role": "user", "content": user_prompt}
    ]

def sanitize_text(s: str, max_len=100000):
    if not s:
        return s
    # remove control chars
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)
    if len(s) > max_len:
        s = s[:max_len] + "\n\n...[truncated]"
    return s

def generate_for_locale(locale: str, seeds, per_seed=1, kb=1, model=DEFAULT_MODEL, dry_run=False, out_file="generated_messages.json", throttle=0.5):
    language_label = LOCALE_TO_LANGUAGE.get(locale, locale)
    out = []
    tokens = _tokens_for_kb(kb)
    print(f"[groq] locale={locale} language={language_label} tokens/request~{tokens}")
    total = len(seeds) * per_seed
    count = 0
    for seed in seeds:
        for i in range(per_seed):
            count += 1
            print(f"[groq] ({count}/{total}) seed='{seed}' ({i+1}/{per_seed})")
            messages = build_prompt(seed, locale, language_label, kb)
            if dry_run:
                # show a preview only
                print("DRY-RUN prompt preview:\n", messages[1]["content"][:800], "...\n")
                out.append({"seed": seed, "visitor_message": None, "preview": messages[1]["content"][:800], "locale": locale})
                time.sleep(throttle)
                continue
            try:
                resp = call_groq(messages, model=model, max_tokens=tokens)
            except Exception as e:
                print("Error calling Groq for seed:", seed, "err:", e)
                out.append({"seed": seed, "visitor_message": None, "error": str(e), "locale": locale})
                # small backoff
                time.sleep(max(throttle, 1.0))
                continue

            # parse
            text = None
            if isinstance(resp, dict):
                text = resp.get("output_text")
                if not text:
                    choices = resp.get("choices") or []
                    if choices:
                        first = choices[0]
                        if isinstance(first, dict):
                            msg = first.get("message") or {}
                            text = msg.get("content") or msg.get("text")
                        elif isinstance(first, str):
                            text = first
            if not text:
                text = str(resp)[:200000]
            text = sanitize_text(text)
            # attach metadata
            out.append({
                "seed": seed,
                "visitor_message": text,
                "locale": locale,
                "model": model,
                "tokens_requested": tokens
            })
            # throttle to respect rate limits
            time.sleep(throttle)
    # write file (append if exists)
    try:
        existing = []
        if os.path.exists(out_file):
            with open(out_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
        combined = existing + out
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(combined, f, ensure_ascii=False, indent=2)
        print("Wrote", out_file, " (total entries now:", len(combined), ")")
    except Exception as e:
        print("Failed to write output file:", e)
    return out

def parse_args_and_run():
    parser = argparse.ArgumentParser(description="Generate Groq messages per locale")
    parser.add_argument("--locale", required=True, help="Locale code, e.g. ta-IN, hi-IN, en-GB")
    parser.add_argument("--per-seed", type=int, default=3, help="Messages to generate per seed")
    parser.add_argument("--kb", type=float, default=1.0, help="Approx KB of each message (affects tokens)")
    parser.add_argument("--out", default="generated_messages.json", help="Output JSON file")
    parser.add_argument("--dry-run", action="store_true", help="Print prompt preview without calling Groq")
    parser.add_argument("--seeds-file", help="Optional JSON file with custom seeds (array of strings)")
    parser.add_argument("--throttle", type=float, default=1.5, help="Seconds to sleep between requests (increase to avoid 429)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Groq model id to use")
    args = parser.parse_args()

    if args.seeds_file:
        with open(args.seeds_file, "r", encoding="utf-8") as f:
            seeds = json.load(f)
    else:
        seeds = DEFAULT_SEEDS

    # basic validation
    if args.locale not in LOCALE_TO_LANGUAGE:
        print(f"Warning: locale '{args.locale}' not in built map. Using locale label = locale code.")
    # call generate
    generate_for_locale(locale=args.locale, seeds=seeds, per_seed=args.per_seed, kb=args.kb,
                        model=args.model, dry_run=args.dry_run, out_file=args.out, throttle=args.throttle)

if __name__ == "__main__":
    parse_args_and_run()
