import pytest
from tests.fixtures.make_synthetic_pdf import build


@pytest.fixture
def synthetic_pdf(tmp_path):
    p = tmp_path / "synthetic.pdf"
    build(str(p))
    return str(p)
