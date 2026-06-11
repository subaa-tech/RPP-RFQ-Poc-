from .models import Dimension, Shape
from .llm import make_client


def fill_missing_dims(doc, runs, client=None, cutoff: float = 0.7):
    """For runs with no / low-confidence dimension, ask the model to read the size
    label (structured response, never drawing on the image). Reconcile with text;
    deterministic length is never overridden."""
    client = client or make_client()
    for run in runs:
        if run.dimension and run.confidence >= cutoff:
            continue
        got = None
        try:
            if doc is not None:
                clip = doc[run.page_index].get_pixmap(dpi=200).tobytes("png")
                res = client.complete_json(
                    "Read the duct size label nearest the highlighted run on this HVAC plan. "
                    'Return JSON {"width_in":int,"height_in":int|null,"round":bool}. '
                    "Do not draw on the image; just report the text.",
                    images=[clip],
                )
                if isinstance(res, dict) and "width_in" in res:
                    got = Dimension(
                        shape=Shape.ROUND if res.get("round") else Shape.RECT,
                        width_in=res["width_in"], height_in=res.get("height_in"),
                        source="vision", confidence=0.8,
                    )
        except Exception:
            got = None
        if got and run.dimension:
            agree = (got.width_in == run.dimension.width_in and got.height_in == run.dimension.height_in)
            run.confidence = 1.0 if agree else 0.6
            run.reasons.append("vision agrees with text" if agree else "VISION/TEXT MISMATCH — needs review")
        elif got and not run.dimension:
            run.dimension = got
            run.confidence = 0.8
            run.reasons.append("dimension from vision (no text match)")
        elif not run.dimension:
            run.confidence = min(run.confidence, 0.4)
            run.reasons.append("no dimension found — flagged for human review")
    return runs
