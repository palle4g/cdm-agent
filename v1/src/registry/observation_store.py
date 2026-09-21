"""
registry/observation_store.py
T-009: The Observation Store - the system's permanent memory.

Stores every conversion, every field mapping, every human correction,
regardless of product type. product_type is just a data column, so this
ONE database serves GovernmentBond, FXForward, and every product added later.
No schema changes needed when a new product is added.

Uses SQLite for the prototype (zero setup, single file). The spec calls for
PostgreSQL in production - swapping the connection later requires no changes
to the functions below, only the connection string.
"""

import sqlite3
import json
import hashlib
import os
import sys
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from config import BASE_DIR

DB_PATH = os.path.join(BASE_DIR, "data", "observation_store.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create all tables if they don't exist. Safe to run repeatedly."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS conversions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_type TEXT NOT NULL,
            source_format TEXT,
            format_fingerprint TEXT,
            raw_input TEXT,
            cdm_output TEXT,
            agent_model TEXT,
            status TEXT,
            accuracy TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS field_mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversion_id INTEGER NOT NULL,
            source_field TEXT,
            cdm_path TEXT,
            confidence TEXT,
            missing_source_field INTEGER DEFAULT 0,
            reason TEXT,
            transformation TEXT,
            was_corrected INTEGER DEFAULT 0,
            FOREIGN KEY (conversion_id) REFERENCES conversions(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS source_formats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            format_fingerprint TEXT UNIQUE,
            product_type TEXT,
            sample_fields TEXT,
            first_seen TEXT,
            times_seen INTEGER DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS learned_mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            format_fingerprint TEXT,
            source_field TEXT,
            cdm_path TEXT,
            success_count INTEGER DEFAULT 1,
            last_used TEXT,
            UNIQUE(format_fingerprint, source_field, cdm_path)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversion_id INTEGER NOT NULL,
            field_mapping_id INTEGER,
            source_field TEXT,
            original_cdm_path TEXT,
            corrected_cdm_path TEXT,
            reason TEXT,
            reviewer TEXT,
            corrected_at TEXT,
            FOREIGN KEY (conversion_id) REFERENCES conversions(id)
        )
    """)

    conn.commit()
    conn.close()
    print("Observation Store initialized at: " + DB_PATH)


def fingerprint_format(normalized_fields):
    """
    Deterministic fingerprint for a source format, based on its field NAMES
    (not values). Same field names in same order = same format = same fingerprint.
    This is how the system recognizes 'I have seen this format before'.
    """
    field_names = sorted([k for k in normalized_fields.keys() if not k.startswith("_")])
    joined = "|".join(field_names)
    return hashlib.sha256(joined.encode()).hexdigest()[:16]


def store_conversion(product_type, normalized_fields, agent_output, accuracy=None):
    """
    Store one conversion and all its field mappings.
    Returns the conversion_id.
    Works identically regardless of product_type - no per-product code.
    """
    conn = get_connection()
    cur = conn.cursor()

    fingerprint = fingerprint_format(normalized_fields)
    source_format = normalized_fields.get("_format", "UNKNOWN")
    raw_input = json.dumps({k: v for k, v in normalized_fields.items() if not k.startswith("_")})
    cdm_output = json.dumps(agent_output.get("cdmTrade", {}))
    agent_model = agent_output.get("_agentModel", "unknown")
    status = "ERROR" if "error" in agent_output else "MAPPED"
    now = datetime.now().isoformat()

    cur.execute("""
        INSERT INTO conversions
        (product_type, source_format, format_fingerprint, raw_input, cdm_output, agent_model, status, accuracy, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (product_type, source_format, fingerprint, raw_input, cdm_output, agent_model, status, accuracy, now))
    conversion_id = cur.lastrowid

    for fm in agent_output.get("fieldMapping", []):
        cur.execute("""
            INSERT INTO field_mappings
            (conversion_id, source_field, cdm_path, confidence, missing_source_field, reason, transformation)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            conversion_id,
            fm.get("sourceField", ""),
            fm.get("cdmPath", ""),
            fm.get("confidence", ""),
            1 if fm.get("missingSourceField", False) else 0,
            fm.get("reason", ""),
            fm.get("transformation", "")
        ))

        # Update learned_mappings so this format gets faster/cheaper over time
        cur.execute("""
            INSERT INTO learned_mappings (format_fingerprint, source_field, cdm_path, success_count, last_used)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(format_fingerprint, source_field, cdm_path)
            DO UPDATE SET success_count = success_count + 1, last_used = excluded.last_used
        """, (fingerprint, fm.get("sourceField", ""), fm.get("cdmPath", ""), now))

    # Track / update the source format catalog
    field_names = ",".join(sorted([k for k in normalized_fields.keys() if not k.startswith("_")]))
    cur.execute("""
        INSERT INTO source_formats (format_fingerprint, product_type, sample_fields, first_seen, times_seen)
        VALUES (?, ?, ?, ?, 1)
        ON CONFLICT(format_fingerprint)
        DO UPDATE SET times_seen = times_seen + 1
    """, (fingerprint, product_type, field_names, now))

    conn.commit()
    conn.close()
    return conversion_id


def get_learned_mappings(normalized_fields):
    """
    Look up whether this exact source format has been seen before, and if so
    return its previously successful field mappings. Used as few-shot context
    for the agent on repeat formats - this is the 'learning' part of the loop.
    """
    fingerprint = fingerprint_format(normalized_fields)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT source_field, cdm_path, success_count FROM learned_mappings
        WHERE format_fingerprint = ?
        ORDER BY success_count DESC
    """, (fingerprint,))
    rows = cur.fetchall()
    conn.close()
    return [{"sourceField": r["source_field"], "cdmPath": r["cdm_path"], "successCount": r["success_count"]} for r in rows]


def record_correction(conversion_id, field_mapping_id, source_field, original_path, corrected_path, reason, reviewer):
    """Record a human correction. Also updates the field_mappings row as corrected."""
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().isoformat()
    cur.execute("""
        INSERT INTO corrections
        (conversion_id, field_mapping_id, source_field, original_cdm_path, corrected_cdm_path, reason, reviewer, corrected_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (conversion_id, field_mapping_id, source_field, original_path, corrected_path, reason, reviewer, now))

    if field_mapping_id:
        cur.execute("UPDATE field_mappings SET was_corrected = 1, cdm_path = ? WHERE id = ?", (corrected_path, field_mapping_id))

    conn.commit()
    conn.close()


def get_stats():
    """Summary stats across all products - proves the store is product-agnostic."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT product_type, COUNT(*) as cnt FROM conversions GROUP BY product_type")
    by_product = {r["product_type"]: r["cnt"] for r in cur.fetchall()}

    cur.execute("SELECT COUNT(*) as cnt FROM conversions")
    total = cur.fetchone()["cnt"]

    cur.execute("SELECT COUNT(*) as cnt FROM source_formats")
    formats_seen = cur.fetchone()["cnt"]

    cur.execute("SELECT COUNT(*) as cnt FROM corrections")
    corrections = cur.fetchone()["cnt"]

    conn.close()
    return {
        "totalConversions": total,
        "byProduct": by_product,
        "distinctFormatsSeen": formats_seen,
        "totalCorrections": corrections
    }


if __name__ == "__main__":
    init_db()

    # Demo: store a couple of fake conversions across two DIFFERENT products
    # to prove one database handles both with zero product-specific code.
    fake_bond = {"TRADE_NUM": "DEMO1", "ISIN": "US91282CJL54", "_format": "CSV"}
    fake_bond_output = {
        "cdmTrade": {"tradeIdentifier": [{"assignedIdentifier": [{"identifier": "DEMO1"}]}]},
        "fieldMapping": [{"sourceField": "TRADE_NUM", "cdmPath": "tradeIdentifier[0].assignedIdentifier[0].identifier", "confidence": "HIGH"}],
        "_agentModel": "claude-sonnet-4-6"
    }
    cid1 = store_conversion("GovernmentBond", fake_bond, fake_bond_output, accuracy="100.0%")
    print("Stored bond conversion, id=" + str(cid1))

    fake_fx = {"TRD_ID": "DEMO2", "BUY_CCY": "EUR", "_format": "CSV"}
    fake_fx_output = {
        "cdmTrade": {"tradeIdentifier": [{"assignedIdentifier": [{"identifier": "DEMO2"}]}]},
        "fieldMapping": [{"sourceField": "TRD_ID", "cdmPath": "tradeIdentifier[0].assignedIdentifier[0].identifier", "confidence": "HIGH"}],
        "_agentModel": "claude-sonnet-4-6"
    }
    cid2 = store_conversion("FXForward", fake_fx, fake_fx_output, accuracy="100.0%")
    print("Stored FX conversion, id=" + str(cid2))

    # Prove the learning loop: same bond format seen again should show learned mappings
    learned = get_learned_mappings(fake_bond)
    print("\nLearned mappings for this bond format (seen before): " + str(len(learned)) + " entries")
    for l in learned:
        print("  " + l["sourceField"] + " -> " + l["cdmPath"] + " (used " + str(l["successCount"]) + "x)")

    print("\nOverall stats (proves ONE store handles BOTH products):")
    stats = get_stats()
    print(json.dumps(stats, indent=2))
