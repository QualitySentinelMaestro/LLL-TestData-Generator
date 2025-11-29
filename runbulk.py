# run_bulk_direct.py
from TestcaseTokens import generate_bulk_rate_safe

seeds = [
    "FAQ about warranty + order lookup + long complaint (Tamil + English)",
    "Order tracking long form and address correction",
    "Returns policy + API error + JSON payload included",
    "Product recommendation + warranty transfer request"
]

# tune these:
PER_SEED = 25        # messages per seed -> total = len(seeds)*PER_SEED
KB = 1               # ~1 KB each (adjust smaller/larger)
THROTTLE = 3.0       # seconds delay between requests (see note below)
OUT = "generated_messages.json"

generate_bulk_rate_safe(seeds, per_seed=PER_SEED, kb=KB, out_file=OUT, throttle_delay=THROTTLE)
