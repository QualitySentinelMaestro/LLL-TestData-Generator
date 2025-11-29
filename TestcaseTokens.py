# rate_safe_groq.py  -- drop-in patches for your generator
import os, json, time, requests
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
import os, json, time, requests
from dotenv import load_dotenv
load_dotenv()  # <-- THIS loads .env into environment variables


GROQ_API_KEY = os.getenv("GROQ_API_KEY")
print("Key loaded:", bool(GROQ_API_KEY))

GROQ_API_URL = os.getenv("GROQ_API_URL")
print("Key loaded:", bool(GROQ_API_URL))

DEFAULT_MODEL = "llama-3.1-8b-instant"
HEADERS = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}



def _tokens_for_kb(kb):
    # rough estimate: ~4 chars per token
    return max(32, int(kb * 1024 // 4))

def _sleep_from_retry_headers(r):
    # prefer 'retry-after' header (seconds) if present
    retry_after = r.headers.get("retry-after")
    if retry_after:
        try:
            # sometimes header is small float or int in seconds
            return float(retry_after)
        except Exception:
            pass
    # fallback: attempt to parse ms from message like "Please try again in 420ms"
    body = (r.text or "").lower()
    import re
    m = re.search(r"try again in (\d+)ms", body)
    if m:
        try:
            return int(m.group(1)) / 1000.0 + 0.05
        except:
            pass
    # final fallback: short backoff
    return 1.0

@retry(wait=wait_exponential(multiplier=0.5, min=0.5, max=10), stop=stop_after_attempt(4),
       retry=retry_if_exception_type((requests.exceptions.RequestException,)))
def call_groq_once(prompt_seed: str, kb:int=1, model=DEFAULT_MODEL, max_tokens=None):
    instruction = (
        f"Generate a single long visitor message (~{kb} KB) for testing a customer support chatbot. "
        "Include Tamil text, emojis, some repeated characters, optionally a small code snippet and a small JSON block. "
        "Return only the message content with no commentary."
    )
    messages = [
        {"role":"system", "content": "You are a test-case generator."},
        {"role":"user", "content": instruction + "\nSeed: " + prompt_seed}
    ]
    if max_tokens is None:
        max_tokens = _tokens_for_kb(kb)
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens}
    r = requests.post(GROQ_API_URL, json=payload, headers=HEADERS, timeout=120)

    # handle 429 specially — return helpful info to caller
    if r.status_code == 429:
        sleep_for = _sleep_from_retry_headers(r)
        print(f"[groq] 429 rate-limit — sleeping {sleep_for}s (retry-after header or server message).")
        time.sleep(sleep_for)
        # raise to let tenacity retry (or caller can loop)
        r.raise_for_status()

    if not (200 <= r.status_code < 300):
        # print debug and raise
        print("=== GROQ CALL FAILED ===")
        print("Status:", r.status_code)
        print("Response headers:", dict(r.headers))
        print("Response body:", r.text[:2000])
        r.raise_for_status()

    return r

def generate_bulk_rate_safe(seeds, per_seed=1, kb=1, out_file="generated_messages.json", throttle_delay=0.5, safety_token_threshold=200):
    """
    Generates messages but respects per-minute token limits using headers and server 429.
    throttle_delay: minimal delay between requests (seconds)
    safety_token_threshold: stop if x-ratelimit-remaining-tokens <= threshold
    """
    out = []
    tokens_per_req = _tokens_for_kb(kb)
    estimated_req_per_min = None
    print(f"[groq] tokens per request (approx): {tokens_per_req}")

    for s in seeds:
        for i in range(per_seed):
            print(f"[groq] generating for seed='{s}' ({i+1}/{per_seed})")
            try:
                r = call_groq_once(s, kb=kb)
            except Exception as e:
                print("[groq] error calling groq:", repr(e))
                out.append({"seed": s, "visitor_message": None, "error": str(e)})
                # short sleep before next to avoid tight retry loops
                time.sleep(max(1.0, throttle_delay))
                continue

            # successful response
            try:
                resp = r.json()
            except Exception:
                text = r.text
                out.append({"seed": s, "visitor_message": text})
                # inspect headers for rate-limit signals
                remaining_tokens = r.headers.get("x-ratelimit-remaining-tokens")
                if remaining_tokens:
                    remaining_tokens = float(remaining_tokens)
                    print(f"[groq] remaining tokens: {remaining_tokens}")
                    if remaining_tokens <= safety_token_threshold:
                        print(f"[groq] remaining tokens {remaining_tokens} <= safety threshold {safety_token_threshold}: stopping early.")
                        with open(out_file, "w", encoding="utf-8") as f:
                            json.dump(out, f, ensure_ascii=False, indent=2)
                        return out_file
                time.sleep(throttle_delay)
                continue

            # parse the assistant content
            text = None
            text = resp.get("output_text")
            if not text:
                choices = resp.get("choices") or []
                if choices:
                    msg = choices[0].get("message") if isinstance(choices[0], dict) else choices[0]
                    if isinstance(msg, dict):
                        text = msg.get("content") or msg.get("text")
                    elif isinstance(msg, str):
                        text = msg
            if not text:
                text = json.dumps(resp)
            out.append({"seed": s, "visitor_message": text})

            # check rate-limit headers and act
            remaining_tokens = r.headers.get("x-ratelimit-remaining-tokens")
            if remaining_tokens:
                try:
                    remaining_tokens = float(remaining_tokens)
                    print(f"[groq] remaining tokens after request: {remaining_tokens}")
                    # if we are close to limit, pause until reset window (we can read reset header or use safe sleep)
                    if remaining_tokens <= safety_token_threshold:
                        reset_info = r.headers.get("x-ratelimit-reset-tokens")
                        print(f"[groq] remaining tokens low ({remaining_tokens}). Header x-ratelimit-reset-tokens: {reset_info}")
                        # parse reset seconds if present in header like "59.34s" or "2m30s"
                        if reset_info and "s" in reset_info:
                            # try to parse float seconds
                            try:
                                sec = float(reset_info.replace("s",""))
                            except:
                                sec = 60
                        else:
                            sec = 60
                        wait = sec + 1.0
                        print(f"[groq] sleeping for {wait}s to allow token bucket to replenish.")
                        time.sleep(wait)
                except Exception:
                    pass

            # small inter-request delay to avoid bursts
            time.sleep(throttle_delay)

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("Wrote", out_file)
    return out_file
