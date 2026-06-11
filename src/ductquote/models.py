from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field


class SystemType(str, Enum):
    SUPPLY = "supply"
    RETURN = "return"
    EXHAUST = "exhaust"
    UNKNOWN = "unknown"


class Shape(str, Enum):
    RECT = "rect"
    ROUND = "round"


class FittingType(str, Enum):
    ELBOW_90 = "elbow_90"
    ELBOW_45 = "elbow_45"
    TEE = "tee"
    WYE = "wye"
    REDUCER = "reducer"
    TRANSITION = "transition"
    OFFSET = "offset"
    UNKNOWN = "unknown"


class Point(BaseModel):
    x: float
    y: float


class Scale(BaseModel):
    raw: str                       # e.g. '1/8" = 1\'-0"'
    points_to_feet: float          # real feet per PDF point
    source: str                    # "parsed" | "default"


class PageInfo(BaseModel):
    index: int                     # 0-based
    sheet_label: str | None = None  # e.g. "M-101"
    title: str = ""
    is_mechanical: bool = False
    score: float = 0.0             # classifier confidence 0..1
    reasons: list[str] = Field(default_factory=list)
    validated_by_vision: bool = False


class Dimension(BaseModel):
    shape: Shape
    width_in: float | None = None  # rect width / round diameter goes in width_in
    height_in: float | None = None  # rect height; None for round
    raw_text: str = ""
    center: Point | None = None
    confidence: float = 1.0
    source: str = "text"           # "text" | "vision"


class DuctSegment(BaseModel):
    p1: Point
    p2: Point
    length_pts: float
    length_ft: float = 0.0
    system: SystemType = SystemType.UNKNOWN


class DuctRun(BaseModel):
    id: str                        # e.g. "M-101-R3"
    page_index: int
    segments: list[DuctSegment]
    length_ft: float
    dimension: Dimension | None = None
    system: SystemType = SystemType.UNKNOWN
    confidence: float = 1.0
    reasons: list[str] = Field(default_factory=list)


class Fitting(BaseModel):
    id: str
    page_index: int
    type: FittingType
    location: Point
    connected_run_ids: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    source: str = "geometry"       # "geometry" | "vision"


class LineItem(BaseModel):
    item_no: int
    description: str               # "Supply duct 12x22, 24 ga galv"
    page_label: str
    shape: Shape
    width_in: float
    height_in: float | None = None
    length_ft: float
    quantity: float = 1.0
    surface_area_sqft: float = 0.0
    gauge: str = ""                # "24 ga"
    weight_lbs: float = 0.0
    material_cost: float = 0.0
    labor_cost: float = 0.0
    overhead_cost: float = 0.0
    freight_cost: float = 0.0
    total_cost: float = 0.0
    sale_price: float = 0.0
    derivation: list[str] = Field(default_factory=list)  # KT: every cent maps to a reason


class Quotation(BaseModel):
    project_name: str
    scale: Scale
    mechanical_pages: list[str]
    line_items: list[LineItem]
    fittings_summary: dict[str, int] = Field(default_factory=dict)
    subtotal_cost: float = 0.0
    margin_pct: float = 0.0
    total_sale_price: float = 0.0
    low_confidence_items: list[str] = Field(default_factory=list)  # human review queue
    generated_for_review: bool = True
