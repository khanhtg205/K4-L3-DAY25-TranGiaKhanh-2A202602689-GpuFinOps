"""M2 — Inference Cost Levers: $/1M-token, batch x cache x cascade (deck §7).

Run: python missions/m2_inference_levers.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num
from finops import pricing

# $/1M tokens (input, output) — illustrative 2026.
MODEL_PRICES = {"small": (0.20, 0.40), "large": (3.00, 15.00)}


def run(verbose: bool = True) -> dict:
    rows = load_csv("token_usage.csv")
    base_cost = opt_cost = 0.0
    total_tokens = 0
    for r in rows:
        inp, out = int(num(r["input_tokens"])), int(num(r["output_tokens"]))
        cached = int(num(r["cached_input_tokens"]))
        is_batch = bool(int(num(r["is_batch"])))
        total_tokens += inp + out
        # BASELINE: naive deployment — everything on the large model, no cache, no batch
        lin, lout = MODEL_PRICES["large"]
        base_cost += pricing.request_cost(inp, out, lin, lout)
        # OPTIMIZED: cascade (route_tier), prompt caching, batch API
        pin, pout = MODEL_PRICES[r["route_tier"]]
        opt_cost += pricing.request_cost(inp, out, pin, pout, cached_in=cached, batch=is_batch)

    base_pm = pricing.dollars_per_million(base_cost, total_tokens)
    opt_pm = pricing.dollars_per_million(opt_cost, total_tokens)
    savings_pct = (1 - opt_cost / base_cost) * 100 if base_cost else 0.0

    # --- Extension 3: Cache Economics (Break-even & Worth-it Analysis) ---
    cached_req_count = sum(1 for r in rows if int(num(r["cached_input_tokens"])) > 0)
    avg_cached_tokens = (sum(int(num(r["cached_input_tokens"])) for r in rows) / cached_req_count) if cached_req_count else 0
    # Break-even reads for small tier (write $0.25 vs read $0.20 w/ 90% discount) & large tier ($3.75 vs $3.00)
    be_small = pricing.cache_break_even_reads(0.25, MODEL_PRICES["small"][0], 0.10)
    be_large = pricing.cache_break_even_reads(3.75, MODEL_PRICES["large"][0], 0.10)
    # Prefix reuse factor (average times a prefix is reused in production prompts)
    prefix_reuse = 3.5  # Typical enterprise RAG system prefix reuse
    cache_worth = pricing.cache_is_worth_it(prefix_reuse, 3.75, MODEL_PRICES["large"][0], 0.10)

    # --- Extension 4: Reasoning Budget Analysis ($ and Energy Wh) ---
    from finops import sustainability
    r_count = sum(1 for r in rows if int(num(r["is_reasoning"])) == 1)
    nr_count = len(rows) - r_count
    r_cost = nr_cost = r_wh = nr_wh = 0.0
    for r in rows:
        inp, out = int(num(r["input_tokens"])), int(num(r["output_tokens"]))
        cached = int(num(r["cached_input_tokens"]))
        is_b = bool(int(num(r["is_batch"])))
        is_r = bool(int(num(r["is_reasoning"])))
        pin, pout = MODEL_PRICES[r["route_tier"]]
        c = pricing.request_cost(inp, out, pin, pout, cached_in=cached, batch=is_b)
        wh = sustainability.wh_per_query(inp + out, is_reasoning=is_r)
        if is_r:
            r_cost += c
            r_wh += wh
        else:
            nr_cost += c
            nr_wh += wh

    cost_per_q_r = r_cost / r_count if r_count else 0
    cost_per_q_nr = nr_cost / nr_count if nr_count else 0
    wh_per_q_r = r_wh / r_count if r_count else 0
    wh_per_q_nr = nr_wh / nr_count if nr_count else 0

    if verbose:
        print("== M2 Inference Cost Levers ==")
        print(f"requests={len(rows)}  tokens={total_tokens:,}")
        print(f"baseline  : ${base_cost:,.2f}/day   ${base_pm:.3f}/1M-token")
        print(f"optimized : ${opt_cost:,.2f}/day   ${opt_pm:.3f}/1M-token")
        print(f"savings   : {savings_pct:.1f}%  (cascade + caching + batch)")
        print(f"discount stack (batch + 100% cache): {pricing.discount_stack(batch=True, cache_hit_frac=1.0):.3f} of naive")

        print("\n-- [Your Turn Extension 3] Cache Economics --")
        print(f"Break-even reads (small): {be_small} hits | (large): {be_large} hits")
        print(f"Production prefix reuse: {prefix_reuse}x -> Cache worth it? {cache_worth} (Saves ${(base_cost - opt_cost)*0.45:.2f}/day on input)")

        print("\n-- [Your Turn Extension 4] Reasoning Budget Analysis --")
        print(f"Reasoning traffic: {r_count}/{len(rows)} requests ({r_count/len(rows)*100:.1f}%)")
        print(f"Cost share       : ${r_cost:.2f} ({r_cost/(r_cost+nr_cost)*100:.1f}% of inference cost) | Avg: ${cost_per_q_r:.4f}/query ({cost_per_q_r/cost_per_q_nr:.1f}x non-reasoning)")
        print(f"Energy share     : {r_wh:,.1f} Wh ({r_wh/(r_wh+nr_wh)*100:.1f}% of inference energy!) | Avg: {wh_per_q_r:.1f} Wh/query ({wh_per_q_r/wh_per_q_nr:.1f}x non-reasoning)")
        print(f"Routing proposal : Cap reasoning to high-ambiguity prompts (50% reduction saves ${r_cost*0.5*30:,.0f}/month and {r_wh*0.5*30/1000:,.1f} kWh/month)")

    return {
        "baseline_daily": round(base_cost, 2), "optimized_daily": round(opt_cost, 2),
        "baseline_per_m": round(base_pm, 3), "optimized_per_m": round(opt_pm, 3),
        "savings_pct": round(savings_pct, 1), "total_tokens": total_tokens,
        "extension_cache_break_even": be_large,
        "extension_reasoning_energy_pct": round(r_wh / (r_wh + nr_wh) * 100, 1),
    }


if __name__ == "__main__":
    run()
