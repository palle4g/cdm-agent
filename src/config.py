"""
config.py
Central configuration for the CDM Mapping Agent.
ALL tuneable parameters live here. No hardcoded values anywhere else.
Environment variables in .env always override the defaults set here.
See docs/CONFIGURATION_REFERENCE.md for what every setting means.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# -------------------------------------------------------
# RUN MODE
# agent  = Claude maps automatically (needs API key)
# human  = human supplies mapping, no API call
# hybrid = agent maps, human always reviews
# -------------------------------------------------------
RUN_MODE = os.getenv("CDM_RUN_MODE", "agent")

# -------------------------------------------------------
# API PROVIDER & MODEL
# -------------------------------------------------------
PROVIDER = os.getenv("CDM_PROVIDER", "anthropic")
AGENT_MODEL = os.getenv("CDM_AGENT_MODEL", "claude-sonnet-4-6")
AGENT_MODEL_COMPLEX = os.getenv("CDM_AGENT_MODEL_COMPLEX", AGENT_MODEL)
AGENT_MAX_TOKENS = int(os.getenv("CDM_AGENT_MAX_TOKENS", "4000"))

# -------------------------------------------------------
# AGENT BEHAVIOR
# -------------------------------------------------------
MAX_RETRIES = int(os.getenv("CDM_MAX_RETRIES", "3"))
# UNKNOWN forces human review rather than a wrong guess when product cannot be detected
DEFAULT_PRODUCT_TYPE = os.getenv("CDM_DEFAULT_PRODUCT_TYPE", "UNKNOWN")
REVIEW_THRESHOLD = os.getenv("CDM_REVIEW_THRESHOLD", "MEDIUM")

# -------------------------------------------------------
# FILE PATHS
# -------------------------------------------------------
BASE_DIR = os.getenv("CDM_BASE_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
GROUND_TRUTH_DIR = os.getenv("CDM_GROUND_TRUTH_DIR", os.path.join(BASE_DIR, "data", "ground_truth"))
EVAL_REPORT_DIR = os.getenv("CDM_EVAL_REPORT_DIR", os.path.join(BASE_DIR, "data"))
SAMPLE_TRADES_DIR = os.getenv("CDM_SAMPLE_TRADES_DIR", os.path.join(BASE_DIR, "data", "sample_trades"))

# -------------------------------------------------------
# VALIDATION RULES
# -------------------------------------------------------
ISIN_LENGTH = int(os.getenv("CDM_ISIN_LENGTH", "12"))
DEFAULT_DAY_COUNT = os.getenv("CDM_DEFAULT_DAY_COUNT", "ACT/ACT.ICMA")

VALID_DAY_COUNTS = [
    "ACT/ACT.ICMA", "ACT/ACT.ISDA", "ACT/ACT.ISMA", "ACT/ACT.AFB",
    "ACT/360", "ACT/365.FIXED", "ACT/365L", "30/360", "30E/360",
    "30E/360.ISDA", "1/1"
]

ISIN_CURRENCY_MAP = {
    "US": "USD", "GB": "GBP", "DE": "EUR", "FR": "EUR", "JP": "JPY",
    "AU": "AUD", "CA": "CAD", "CH": "CHF", "HK": "HKD", "SG": "SGD",
    "IT": "EUR", "ES": "EUR", "NL": "EUR"
}

# -------------------------------------------------------
# CDM VERSION & LOGGING
# -------------------------------------------------------
CDM_VERSION = os.getenv("CDM_VERSION", "7.3.0")
LOG_LEVEL = os.getenv("CDM_LOG_LEVEL", "INFO")
LOG_AGENT_RESPONSES = os.getenv("CDM_LOG_AGENT_RESPONSES", "false").lower() == "true"


def print_config():
    print("=" * 50)
    print("CDM MAPPING AGENT - Current Configuration")
    print("=" * 50)
    print("Run mode:          " + RUN_MODE)
    print("Provider:          " + PROVIDER)
    print("Model (standard):  " + AGENT_MODEL)
    print("Model (complex):   " + AGENT_MODEL_COMPLEX)
    print("Max tokens:        " + str(AGENT_MAX_TOKENS))
    print("Max retries:       " + str(MAX_RETRIES))
    print("Default product:   " + DEFAULT_PRODUCT_TYPE)
    print("Review threshold:  " + REVIEW_THRESHOLD)
    print("CDM version:       " + CDM_VERSION)
    print("Base dir:          " + BASE_DIR)
    print("Ground truth dir:  " + GROUND_TRUTH_DIR)
    print("Default day count: " + DEFAULT_DAY_COUNT)
    print("=" * 50)


if __name__ == "__main__":
    print_config()
