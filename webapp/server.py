import uuid
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from src.ductquote.pipeline import run_pipeline
from src.ductquote.pricing import reprice_items

app = FastAPI(title="RFP/RFQ Vortex Sample POC")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)
STATIC = Path(__file__).resolve().parent / "static"


@app.get("/api/health")
def health():
    return {"ok": True, "product": "RFP/RFQ Vortex Sample POC"}


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...), project: str = Form("Project"),
                  use_llm: str = Form("false"), scale: str = Form("auto")):
    job = uuid.uuid4().hex[:8]
    job_dir = OUT / job
    job_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = job_dir / "input.pdf"
    pdf_path.write_bytes(await file.read())
    q = run_pipeline(str(pdf_path), project, str(job_dir),
                     use_llm=(use_llm.lower() == "true"), scale_choice=scale)
    imgs = [f"/output/{job}/{p.name}" for p in sorted(job_dir.glob("annotated_p*.png"))]
    data = q.model_dump()
    data["annotated_images"] = imgs
    data["job"] = job
    return JSONResponse(data)


class RepriceReq(BaseModel):
    line_items: list[dict]
    margin_pct: float = 0.25
    finalize: bool = False


@app.post("/api/reprice")
def reprice(req: RepriceReq):
    result = reprice_items(req.line_items, req.margin_pct)
    result["approved"] = bool(req.finalize)
    return JSONResponse(result)


app.mount("/output", StaticFiles(directory=str(OUT)), name="output")
app.mount("/", StaticFiles(directory=str(STATIC), html=True), name="static")
