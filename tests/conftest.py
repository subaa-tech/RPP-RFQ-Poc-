import pytest
from tests.fixtures.make_synthetic_pdf import build, build_raster, build_shx


@pytest.fixture
def synthetic_pdf(tmp_path):
    p = tmp_path / "synthetic.pdf"
    build(str(p))
    return str(p)


@pytest.fixture
def raster_pdf(tmp_path):
    p = tmp_path / "raster.pdf"
    build_raster(str(p))
    return str(p)


@pytest.fixture
def shx_pdf(tmp_path):
    p = tmp_path / "shx.pdf"
    build_shx(str(p))
    return str(p)
