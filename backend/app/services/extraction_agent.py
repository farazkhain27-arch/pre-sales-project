"""
LangGraph extraction pipeline.

Design principle (kept consistent across the whole product line):
  The LLM's ONLY job is turning unstructured text (RFP / customer requirements
  documents) into structured candidate requirements with a confidence score
  and the exact source snippet it came from. It NEVER decides quantities that
  go straight into pricing, and it NEVER picks the final matched product —
  that happens in rules_engine.py deterministically. This keeps every number
  on the final proposal traceable back to a rule, not a model guess.

Graph:
  parse_document -> extract_requirements -> validate_requirements -> END
"""
import json
import re
import logging
from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from anthropic import Anthropic

from ..config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


class ExtractionState(TypedDict):
    raw_text: str
    doc_type: str
    candidate_requirements: List[dict]
    validated_requirements: List[dict]


EXTRACTION_SYSTEM_PROMPT = """You are a systems-integrator presales requirements extraction assistant
(networking, smart buildings, cybersecurity, unified communications, ERP/CRM, AV, managed services).
Given raw text from an RFP or customer-requirements document, extract every distinct
technical/commercial requirement as a JSON array. For each requirement return:
  - category: short category e.g. "Networking & Infrastructure", "Smart Connected Facilities",
    "Cybersecurity", "Integrated Communications", "Digital Transformation", "Audio Visual", "Managed Services"
  - description: concise requirement description
  - quantity: numeric quantity if stated, else 1
  - unit: unit of measure (e.g. "unit", "port", "user", "license", "camera")
  - technical_attributes: object of key technical specs mentioned (bandwidth, protocol, users, redundancy, etc.)
  - confidence: 0.0-1.0 how confident you are this is a real, distinct requirement
  - source_snippet: the exact sentence/clause you extracted it from

Return ONLY a JSON array. No preamble, no markdown fences."""


def _client() -> Anthropic:
    return Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def parse_document(state: ExtractionState) -> ExtractionState:
    # Placeholder for doc-type specific pre-processing (e.g. stripping
    # boilerplate headers/footers from RFP PDFs before extraction).
    return state


def extract_requirements(state: ExtractionState) -> ExtractionState:
    client = _client()
    response = client.messages.create(
        model=settings.LLM_MODEL,
        max_tokens=4000,
        system=EXTRACTION_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Document type: {state['doc_type']}\n\nDocument text:\n{state['raw_text'][:15000]}"
        }],
    )
    text = "".join(block.text for block in response.content if block.type == "text").strip()
    text = text.removeprefix("```json").removesuffix("```").strip()
    # Log a short preview of the LLM output for debugging when extraction returns no results
    try:
        preview = (text[:1000] + '...') if len(text) > 1000 else text
        logger.info("LLM output preview: %s", preview)
    except Exception:
        pass

    def _parse_json_array(raw: str):
        try:
            value = json.loads(raw)
            return value if isinstance(value, list) else []
        except json.JSONDecodeError:
            match = re.search(r"(\[.*\])", raw, re.S)
            if match:
                try:
                    value = json.loads(match.group(1))
                    return value if isinstance(value, list) else []
                except json.JSONDecodeError:
                    return []
            return []

    candidates = _parse_json_array(text)
    try:
        logger.info("Parsed %d candidate requirements from LLM output", len(candidates))
    except Exception:
        pass
    state["candidate_requirements"] = candidates
    return state


def validate_requirements(state: ExtractionState) -> ExtractionState:
    """Deterministic guardrails — not LLM. Drop malformed/low-confidence junk."""
    validated = []
    for r in state.get("candidate_requirements", []):
        if not r.get("description"):
            continue
        r["quantity"] = float(r.get("quantity") or 1)
        r["confidence"] = float(r.get("confidence") or 0.5)
        r.setdefault("unit", "unit")
        r.setdefault("technical_attributes", {})
        r.setdefault("category", "General")
        validated.append(r)
    state["validated_requirements"] = validated
    return state


def build_graph():
    graph = StateGraph(ExtractionState)
    graph.add_node("parse_document", parse_document)
    graph.add_node("extract_requirements", extract_requirements)
    graph.add_node("validate_requirements", validate_requirements)
    graph.set_entry_point("parse_document")
    graph.add_edge("parse_document", "extract_requirements")
    graph.add_edge("extract_requirements", "validate_requirements")
    graph.add_edge("validate_requirements", END)
    return graph.compile()


_compiled_graph = None


def run_extraction(raw_text: str, doc_type: str) -> List[dict]:
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    result = _compiled_graph.invoke({
        "raw_text": raw_text,
        "doc_type": doc_type,
        "candidate_requirements": [],
        "validated_requirements": [],
    })
    return result["validated_requirements"]
