"""Deterministic structured triage for normalized job postings."""

from __future__ import annotations

from dataclasses import dataclass
import re

from .matching import MatchDecision
from .normalization import PostingRecord


@dataclass(frozen=True)
class TriageRecord:
    """Structured, explainable fields used to review one posting."""

    posting_id: str
    role: str
    salary_gbp: float | None
    salary_text: str | None
    location: str | None
    sponsorship: str
    seniority: str
    work_mode: str
    source: str
    source_url: str
    fit_score: int
    route: str
    reason_codes: tuple[str, ...]
    unknowns: tuple[str, ...]
    requires_human_approval: bool


def _metadata(record: PostingRecord, key: str) -> str | None:
    value = record.posting.metadata.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _salary(record: PostingRecord) -> float | None:
    value = _metadata(record, "salary_gbp")
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _salary_text(record: PostingRecord) -> str | None:
    return (
        _metadata(record, "salary_text")
        or _metadata(record, "salary_range")
        or _metadata(record, "salary")
    )


def _sponsorship(record: PostingRecord) -> str:
    configured = _metadata(record, "sponsorship")
    if configured:
        return configured.casefold()
    text = " ".join(
        (
            record.posting.title,
            record.posting.description,
            *record.posting.requirements,
        )
    ).casefold()
    if re.search(r"\b(no|without)\s+(visa\s+)?sponsorship\b", text):
        return "not_available"
    if re.search(r"\b(visa\s+)?sponsorship\s+(available|provided)\b", text):
        return "available"
    if "visa sponsorship" in text or "sponsorship required" in text:
        return "mentioned"
    return "unknown"


def _seniority(record: PostingRecord) -> str:
    configured = _metadata(record, "seniority")
    if configured:
        return configured.casefold()
    title = record.posting.title.casefold()
    for label, terms in (
        ("intern", ("intern", "internship", "graduate")),
        ("junior", ("junior", "jr")),
        ("senior", ("senior", "sr")),
        ("lead", ("lead", "principal", "staff")),
        ("manager", ("manager", "director", "head of")),
    ):
        if any(re.search(rf"\b{re.escape(term)}\b", title) for term in terms):
            return label
    return "unknown"


def _work_mode(record: PostingRecord) -> str:
    configured = record.posting.remote_mode or _metadata(record, "work_mode")
    if configured:
        return configured.casefold()
    text = " ".join((record.posting.title, record.posting.description)).casefold()
    if "hybrid" in text:
        return "hybrid"
    if re.search(r"\b(remote|work from home|wfh)\b", text):
        return "remote"
    if re.search(r"\b(onsite|on-site|office-based)\b", text):
        return "onsite"
    return "unknown"


def triage_posting(record: PostingRecord, decision: MatchDecision) -> TriageRecord:
    """Extract triage fields and map a match decision to a safe review route."""
    role = _metadata(record, "role") or record.posting.title.strip()
    location = record.posting.location or _metadata(record, "location")
    unknowns = list(decision.unknowns)
    if location is None:
        unknowns.append("location_missing")
    salary = _salary(record)
    if salary is None:
        unknowns.append("salary_missing")
    sponsorship = _sponsorship(record)
    if sponsorship == "unknown":
        unknowns.append("sponsorship_missing")
    seniority = _seniority(record)
    if seniority == "unknown":
        unknowns.append("seniority_missing")
    work_mode = _work_mode(record)
    if work_mode == "unknown":
        unknowns.append("work_mode_missing")

    if decision.excluded:
        route = "park"
    elif decision.matched:
        route = "draft_for_approval"
    else:
        route = "review"

    reason_codes = list(decision.reasons)
    if decision.matched:
        reason_codes.append("profile_match")
    if record.posting.source_name:
        reason_codes.append(f"source:{record.posting.source_name}")

    return TriageRecord(
        posting_id=record.stable_id,
        role=role,
        salary_gbp=salary,
        salary_text=_salary_text(record),
        location=location,
        sponsorship=sponsorship,
        seniority=seniority,
        work_mode=work_mode,
        source=record.posting.source_name,
        source_url=record.source_url,
        fit_score=decision.score,
        route=route,
        reason_codes=tuple(dict.fromkeys(reason_codes)),
        unknowns=tuple(dict.fromkeys(unknowns)),
        requires_human_approval=route != "park",
    )
