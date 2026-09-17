"""
view_store.py
Quick command-line viewer for the Observation Store.
Run from the project root: python view_store.py

Usage:
    python view_store.py                    (overall stats)
    python view_store.py GovernmentBond      (all conversions for one product)
    python view_store.py formats             (every distinct source format seen)
"""

import sys
import os
import json

sys.path.append("src")
from registry.observation_store import get_connection, get_stats


def show_stats():
    stats = get_stats()
    print("=" * 50)
    print("OBSERVATION STORE - OVERVIEW")
    print("=" * 50)
    print("Total conversions:  " + str(stats["totalConversions"]))
    print("Distinct formats:   " + str(stats["distinctFormatsSeen"]))
    print("Total corrections:  " + str(stats["totalCorrections"]))
    print("\nBy product:")
    for product, count in stats["byProduct"].items():
        print("  " + product + ": " + str(count))


def show_product(product_type):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, source_format, agent_model, status, accuracy, created_at
        FROM conversions WHERE product_type = ?
        ORDER BY created_at DESC
    """, (product_type,))
    rows = cur.fetchall()
    conn.close()

    print("=" * 50)
    print("CONVERSIONS FOR: " + product_type)
    print("=" * 50)
    if not rows:
        print("No conversions stored yet for this product.")
        return
    for r in rows:
        print("  id=" + str(r["id"]) + " | " + r["source_format"] + " | " + r["agent_model"] + " | " + r["status"] + " | " + str(r["accuracy"]) + " | " + r["created_at"])


def show_formats():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT format_fingerprint, product_type, times_seen, sample_fields FROM source_formats ORDER BY times_seen DESC")
    rows = cur.fetchall()
    conn.close()

    print("=" * 50)
    print("KNOWN SOURCE FORMATS")
    print("=" * 50)
    if not rows:
        print("No formats recorded yet.")
        return
    for r in rows:
        print("  " + r["format_fingerprint"] + " | " + r["product_type"] + " | seen " + str(r["times_seen"]) + "x")
        print("    fields: " + r["sample_fields"])


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    if arg is None:
        show_stats()
    elif arg == "formats":
        show_formats()
    else:
        show_product(arg)
