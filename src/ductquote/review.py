def build_review_report(runs, cutoff: float = 0.7) -> str:
    low = [r for r in runs if r.confidence < cutoff]
    lines = ["# Human Review Queue", "", f"{len(low)} item(s) below confidence {cutoff}.", ""]
    for r in low:
        dim = r.dimension.raw_text if r.dimension else "—"
        lines += [
            f"## {r.id} (page {r.page_index + 1}) — confidence {r.confidence:.2f}",
            f"- Dimension: {dim}",
            f"- Length (deterministic): {r.length_ft} ft",
            f"- Reasons: {'; '.join(r.reasons)}",
            f"- Action: verify against annotated_p{r.page_index + 1}.png and approve/edit",
            "",
        ]
    return "\n".join(lines)
