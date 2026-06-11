from src.ductquote.models import PageInfo
from src.ductquote.llm import NullClient
from src.ductquote.vision_validate import validate_mechanical


def test_validate_passthrough_with_null_client():
    pages = [PageInfo(index=0, sheet_label="M-101", is_mechanical=True, score=0.9)]
    out = validate_mechanical(None, pages, client=NullClient())
    assert out[0].validated_by_vision is True


def test_validate_fail_closed_drops_low_score():
    pages = [PageInfo(index=5, sheet_label="M-700", is_mechanical=True, score=0.5)]
    out = validate_mechanical(None, pages, client=NullClient(fail=True))
    assert out[0].is_mechanical is False
