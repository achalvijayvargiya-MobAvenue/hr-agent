"""Parse hr_agent logs and estimate LLM costs per module."""
from __future__ import annotations

import re
from pathlib import Path

PRICES = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "text-embedding-3-small": {"input": 0.02, "output": 0.0},
}


def cost_usd(model: str, prompt: int, completion: int) -> float:
    p = PRICES.get(model, PRICES["gpt-4o-mini"])
    return (prompt * p["input"] + completion * p["output"]) / 1_000_000


def parse_logs(logs_dir: Path) -> dict:
    extract_start = re.compile(
        r"\[EXTRACT\] Starting (JD|CV) extraction.*model: ([\w.-]+)"
    )
    extract_usage = re.compile(
        r"\[EXTRACT\] LLM usage — prompt_tokens: (\d+)  completion_tokens: (\d+)  total: (\d+)"
    )
    embed_usage = re.compile(
        r"\[EMBED\] Embedding API usage — prompt_tokens: (\d+)  total_tokens: (\d+)"
    )
    rerank_model = re.compile(
        r"\[RERANK\] Sending top \d+ candidates.* to ([\w.-]+) for reranking"
    )
    rerank_usage = re.compile(
        r"\[RERANK\] LLM usage — prompt_tokens: (\d+)  completion_tokens: (\d+)  total: (\d+)"
    )

    positions: list[dict] = []
    candidates: list[dict] = []
    matches: list[dict] = []

    last_extract_type: str | None = None
    last_extract_model = "gpt-4o-mini"
    pending_rerank_model: str | None = None

    for log_file in sorted(logs_dir.glob("hr_agent.log*")):
        text = log_file.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            m = extract_start.search(line)
            if m:
                last_extract_type = m.group(1)
                last_extract_model = m.group(2)
                continue

            m = extract_usage.search(line)
            if m:
                pt, ct, _ = map(int, m.groups())
                entry = {
                    "model": last_extract_model,
                    "prompt": pt,
                    "completion": ct,
                    "cost": cost_usd(last_extract_model, pt, ct),
                }
                if last_extract_type == "JD":
                    positions.append({"extract": entry})
                elif last_extract_type == "CV":
                    candidates.append({"extract": entry})
                continue

            m = embed_usage.search(line)
            if m:
                pt, _ = map(int, m.groups())
                entry = {
                    "model": "text-embedding-3-small",
                    "prompt": pt,
                    "cost": cost_usd("text-embedding-3-small", pt, 0),
                }
                if positions and "embed" not in positions[-1]:
                    positions[-1]["embed"] = entry
                elif candidates and "embed" not in candidates[-1]:
                    candidates[-1]["embed"] = entry
                continue

            m = rerank_model.search(line)
            if m:
                pending_rerank_model = m.group(1)
                continue

            m = rerank_usage.search(line)
            if m:
                pt, ct, _ = map(int, m.groups())
                model = pending_rerank_model or "gpt-4o"
                matches.append(
                    {
                        "model": model,
                        "prompt": pt,
                        "completion": ct,
                        "cost": cost_usd(model, pt, ct),
                    }
                )
                pending_rerank_model = None

    def unit_cost(item: dict) -> float:
        total = item.get("extract", {}).get("cost", 0.0)
        total += item.get("embed", {}).get("cost", 0.0)
        return total

    def summarize(items: list[dict], cost_fn) -> tuple[float, float]:
        if not items:
            return 0.0, 0.0
        costs = [cost_fn(i) for i in items]
        return sum(costs), sum(costs) / len(costs)

    pos_total, pos_avg = summarize(positions, unit_cost)
    cand_total, cand_avg = summarize(candidates, unit_cost)
    match_total, match_avg = summarize(matches, lambda m: m["cost"])

    return {
        "positions": positions,
        "candidates": candidates,
        "matches": matches,
        "pos_total": pos_total,
        "pos_avg": pos_avg,
        "cand_total": cand_total,
        "cand_avg": cand_avg,
        "match_total": match_total,
        "match_avg": match_avg,
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    logs_dir = root / "logs"
    r = parse_logs(logs_dir)
    grand = r["pos_total"] + r["cand_total"] + r["match_total"]

    print("=== HR Agent LLM Cost Report (from local logs) ===\n")
    print(f"Log files scanned: {len(list(logs_dir.glob('hr_agent.log*')))}")
    print(f"Positions processed: {len(r['positions'])}")
    print(f"Candidates processed: {len(r['candidates'])}")
    print(f"Match runs (with rerank): {len(r['matches'])}\n")

    print("| Module    | Count | Total cost | Avg per unit |")
    print("|-----------|-------|------------|--------------|")
    print(f"| Position  | {len(r['positions']):5} | ${r['pos_total']:.6f}  | ${r['pos_avg']:.6f}     |")
    print(f"| Candidate | {len(r['candidates']):5} | ${r['cand_total']:.6f}  | ${r['cand_avg']:.6f}     |")
    print(f"| Matching  | {len(r['matches']):5} | ${r['match_total']:.6f}  | ${r['match_avg']:.6f}     |")
    print(f"| TOTAL     |       | ${grand:.6f}  |              |\n")

    if r["positions"]:
        p = r["positions"][0]
        e = p["extract"]
        print("Sample position:")
        print(f"  Extraction ({e['model']}): {e['prompt']} in / {e['completion']} out = ${e['cost']:.6f}")
        if "embed" in p:
            print(f"  Embedding: {p['embed']['prompt']} tokens = ${p['embed']['cost']:.8f}")

    if r["candidates"]:
        c = r["candidates"][0]
        e = c["extract"]
        print("Sample candidate:")
        print(f"  Extraction ({e['model']}): {e['prompt']} in / {e['completion']} out = ${e['cost']:.6f}")
        if "embed" in c:
            print(f"  Embedding: {c['embed']['prompt']} tokens = ${c['embed']['cost']:.8f}")

    if r["matches"]:
        m = r["matches"][0]
        print(f"Sample match rerank ({m['model']}): {m['prompt']} in / {m['completion']} out = ${m['cost']:.6f}")


if __name__ == "__main__":
    main()
