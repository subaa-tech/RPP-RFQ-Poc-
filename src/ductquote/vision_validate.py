from .models import PageInfo
from .llm import LLMClient, make_client


def validate_mechanical(doc, pages: list[PageInfo], client: LLMClient | None = None) -> list[PageInfo]:
    """Confirm mechanical candidates with vision. Fails CLOSED: if the model
    errors, only score>=0.8 candidates survive."""
    client = client or make_client()
    cands = [p for p in pages if p.is_mechanical]
    try:
        if doc is not None:
            imgs = [doc[p.index].get_pixmap(dpi=80).tobytes("png") for p in cands]
            res = client.complete_json(
                "You are validating HVAC ductwork FLOOR PLANS. Return JSON "
                '{"mechanical_indexes":[...]} listing only the 0-based image indexes that are '
                "true duct floor plans (not piping, P&ID, schedules, sections, electrical).",
                images=imgs,
            )
        else:
            res = client.complete_json("validate", images=None)
        if isinstance(res, dict) and "mechanical_indexes" in res:
            keep = set(res["mechanical_indexes"])
            for n, p in enumerate(cands):
                p.validated_by_vision = n in keep
                if not p.validated_by_vision:
                    p.is_mechanical = False
        else:  # null/passthrough: confirm high-confidence, keep as-is
            for p in cands:
                p.validated_by_vision = p.score >= 0.8
    except Exception:
        for p in cands:  # FAIL-CLOSED
            if p.score < 0.8:
                p.is_mechanical = False
            else:
                p.validated_by_vision = False
    return pages
