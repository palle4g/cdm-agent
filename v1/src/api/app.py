"""
api/app.py
FastAPI backend for the Critique UI.
Serves data from the Observation Store, accepts human corrections, and
serves the ground truth corrections log (transparency into changes made to
the answer key itself, separate from the agent's own per-field reasoning).

Run from the project root:
    uvicorn src.api.app:app --reload --port 8000
"""

import os
import sys
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from registry.observation_store import get_connection, init_db, get_stats, record_correction
from config import BASE_DIR

app = FastAPI(title="CDM Mapping Agent - Critique API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

GT_CORRECTIONS_LOG_PATH = os.path.join(BASE_DIR, "data", "ground_truth_corrections_log.json")


class CorrectionRequest(BaseModel):
    conversion_id: int
    field_mapping_id: int
    source_field: str
    original_cdm_path: str
    corrected_cdm_path: str
    reason: str
    reviewer: str


@app.get("/")
def root():
    return {"status": "ok", "message": "CDM Mapping Agent Critique API"}


@app.get("/stats")
def stats():
    return get_stats()


@app.get("/conversions")
def list_conversions(product_type: str = None, status: str = None, limit: int = 50):
    conn = get_connection()
    cur = conn.cursor()
    query = "SELECT * FROM conversions WHERE 1=1"
    params = []
    if product_type:
        query += " AND product_type = ?"
        params.append(product_type)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/conversions/{conversion_id}")
def get_conversion(conversion_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM conversions WHERE id = ?", (conversion_id,))
    conv = cur.fetchone()
    if not conv:
        conn.close()
        raise HTTPException(status_code=404, detail="Conversion not found")
    cur.execute("SELECT * FROM field_mappings WHERE conversion_id = ?", (conversion_id,))
    mappings = cur.fetchall()
    cur.execute("SELECT * FROM corrections WHERE conversion_id = ? ORDER BY corrected_at DESC", (conversion_id,))
    corrections = cur.fetchall()
    conn.close()

    conv_dict = dict(conv)
    conv_dict["raw_input"] = json.loads(conv_dict["raw_input"]) if conv_dict["raw_input"] else {}
    conv_dict["cdm_output"] = json.loads(conv_dict["cdm_output"]) if conv_dict["cdm_output"] else {}
    conv_dict["field_mappings"] = [dict(m) for m in mappings]
    conv_dict["corrections"] = [dict(c) for c in corrections]
    return conv_dict


@app.post("/corrections")
def submit_correction(correction: CorrectionRequest):
    record_correction(
        conversion_id=correction.conversion_id,
        field_mapping_id=correction.field_mapping_id,
        source_field=correction.source_field,
        original_path=correction.original_cdm_path,
        corrected_path=correction.corrected_cdm_path,
        reason=correction.reason,
        reviewer=correction.reviewer
    )
    return {"status": "ok", "message": "Correction recorded"}


@app.get("/products")
def products():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT product_type FROM conversions")
    rows = cur.fetchall()
    conn.close()
    return [r["product_type"] for r in rows]


@app.get("/ground-truth-corrections")
def ground_truth_corrections(product_type: str = None):
    """
    Serves the log of corrections made to the ground truth (answer key) itself,
    with full reasoning for each. This is DIFFERENT from a conversion's own
    fieldMapping 'reason' field - those explain the AI's decision on one trade;
    this explains why the test/scoring methodology itself was changed, so a
    reviewer can see why accuracy numbers moved and trust that changes were
    principled corrections rather than the answer key being adjusted to match
    whatever the AI happened to produce.
    """
    if not os.path.exists(GT_CORRECTIONS_LOG_PATH):
        return []
    with open(GT_CORRECTIONS_LOG_PATH, "r") as f:
        entries = json.load(f)
    if product_type:
        entries = [e for e in entries if e.get("product_type") == product_type]
    return entries
