"""Deterministic profile matching and explainable job scoring."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any
from urllib.parse import urlparse

from .ats import NormalizedPosting


DEFAULT_CLEARANCE_EXCLUSIONS = ("SC", "SC Clearance", "Security Check")
DEFAULT_COMPANY_EXCLUSIONS: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class MatchDecision:
    """The explainable result of evaluating one posting against one profile."""

    profile_name: str
    score: int
    threshold: int
    matched: bool
    excluded: bool
    reasons: tuple[str, ...]
    unknowns: tuple[str, ...]


def _terms(profile: dict[str, Any], key: str) -> tuple[str, ...]:
    values = profile.get("keywords", {}).get(key, [])
    return tuple(value.casefold() for value in values if isinstance(value, str) and value.strip())


def _text(posting: NormalizedPosting) -> str:
    return " ".join(
        (
            posting.title,
            posting.company,
            posting.description,
            *(posting.requirements),
        )
    ).casefold()


def _clearance_matches(
    posting: NormalizedPosting,
    excluded_terms: tuple[str, ...],
) -> tuple[str, ...]:
    """Return configured clearance terms found in structured fields or job text."""
    searchable = " ".join(
        (
            posting.title,
            posting.company,
            posting.description,
            *(posting.requirements),
            *(posting.clearance_requirements),
        )
    ).casefold()
    matches: list[str] = []
    for term in sorted(excluded_terms, key=len, reverse=True):
        normalized = term.strip()
        if not normalized:
            continue
        normalized_folded = normalized.casefold()
        if any(normalized_folded in match for match in matches):
            continue
        pattern = (
            r"\b"
            + r"[-/\s]+".join(re.escape(part) for part in normalized.split())
            + r"\b"
        )
        if re.search(pattern, searchable, flags=re.IGNORECASE):
            matches.append(normalized_folded)
    return tuple(matches)


def _company_matches(
    posting: NormalizedPosting,
    exclusions: tuple[dict[str, Any], ...],
) -> tuple[str, ...]:
    """Return reasons for configured company-name or company-domain matches."""
    company = " ".join(posting.company.casefold().split())
    hostname = (urlparse(posting.source_url).hostname or "").casefold().removeprefix("www.")
    matches: list[str] = []
    for exclusion in exclusions:
        if not isinstance(exclusion, dict):
            continue
        names = [exclusion.get("name"), *exclusion.get("aliases", [])]
        normalized_names = {
            " ".join(value.casefold().split())
            for value in names
            if isinstance(value, str) and value.strip()
        }
        domains = {
            value.casefold().removeprefix("www.").strip()
            for value in exclusion.get("domains", [])
            if isinstance(value, str) and value.strip()
        }
        if company in normalized_names or hostname in domains:
            reason = exclusion.get("reason")
            label = reason.strip() if isinstance(reason, str) and reason.strip() else "configured exclusion"
            matches.append(label)
    return tuple(matches)


def _salary(posting: NormalizedPosting) -> float | None:
    value = posting.metadata.get("salary_gbp")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def match_profile(
    posting: NormalizedPosting,
    profile_name: str,
    profile: dict[str, Any],
    *,
    clearance_exclusions: tuple[str, ...] = DEFAULT_CLEARANCE_EXCLUSIONS,
    company_exclusions: tuple[dict[str, Any], ...] = DEFAULT_COMPANY_EXCLUSIONS,
) -> MatchDecision:
    """Score one posting against one validated profile configuration."""
    if not profile.get("enabled", False):
        return MatchDecision(profile_name, 0, 0, False, True, ("profile_disabled",), ())

    clearance_matches = _clearance_matches(posting, clearance_exclusions)
    threshold = int(profile.get("score_threshold", 100))
    if clearance_matches:
        return MatchDecision(
            profile_name,
            0,
            threshold,
            False,
            True,
            (f"clearance_exclusion:{','.join(clearance_matches)}",),
            (),
        )

    company_matches = _company_matches(posting, company_exclusions)
    if company_matches:
        return MatchDecision(
            profile_name,
            0,
            threshold,
            False,
            True,
            (f"company_exclusion:{'|'.join(company_matches)}",),
            (),
        )

    text = _text(posting)
    reasons: list[str] = []
    unknowns: list[str] = []
    excluded = False
    score = 0

    included = _terms(profile, "include")
    if included:
        matched_keywords = tuple(term for term in included if term in text)
        if matched_keywords:
            score += min(40, 20 * len(matched_keywords))
            reasons.append(f"include_keywords:{','.join(matched_keywords)}")
        else:
            excluded = True
            reasons.append("no_include_keyword_match")

    excluded_keywords = _terms(profile, "exclude")
    blocked = tuple(term for term in excluded_keywords if term in text)
    if blocked:
        excluded = True
        reasons.append(f"excluded_keywords:{','.join(blocked)}")

    employment_types = tuple(
        value.casefold()
        for value in profile.get("employment_types", [])
        if isinstance(value, str)
    )
    if employment_types:
        if posting.employment_type is None:
            unknowns.append("employment_type_missing")
        elif posting.employment_type.casefold() in employment_types:
            score += 20
            reasons.append("employment_type_match")
        else:
            excluded = True
            reasons.append("employment_type_mismatch")

    location_config = profile.get("locations", {})
    included_locations = tuple(
        value.casefold()
        for value in location_config.get("include", [])
        if isinstance(value, str)
    )
    if included_locations:
        location = (posting.location or "").casefold()
        if not location:
            unknowns.append("location_missing")
        elif any(value in location for value in included_locations):
            score += 15
            reasons.append("location_match")
        else:
            excluded = True
            reasons.append("location_mismatch")

    remote_modes = tuple(
        value.casefold()
        for value in profile.get("remote", {}).get("modes", [])
        if isinstance(value, str)
    )
    if remote_modes:
        if posting.remote_mode is None:
            unknowns.append("remote_mode_missing")
        elif posting.remote_mode.casefold() in remote_modes:
            score += 10
            reasons.append("remote_mode_match")
        else:
            excluded = True
            reasons.append("remote_mode_mismatch")

    minimum = profile.get("salary", {}).get("minimum_gbp")
    if minimum is not None:
        salary = _salary(posting)
        if salary is None:
            unknowns.append("salary_missing")
        elif salary >= float(minimum):
            score += 15
            reasons.append("salary_floor_met")
        else:
            excluded = True
            reasons.append("salary_floor_not_met")

    matched = not excluded and score >= threshold
    if not matched and not excluded:
        reasons.append("below_score_threshold")
    return MatchDecision(
        profile_name,
        min(score, 100),
        threshold,
        matched,
        excluded,
        tuple(reasons),
        tuple(unknowns),
    )


def match_enabled_profiles(
    posting: NormalizedPosting,
    profiles: dict[str, dict[str, Any]],
    *,
    clearance_exclusions: tuple[str, ...] = DEFAULT_CLEARANCE_EXCLUSIONS,
    company_exclusions: tuple[dict[str, Any], ...] = DEFAULT_COMPANY_EXCLUSIONS,
) -> tuple[MatchDecision, ...]:
    """Evaluate a posting against all configured profiles in stable order."""
    return tuple(
        match_profile(
            posting,
            name,
            profiles[name],
            clearance_exclusions=clearance_exclusions,
            company_exclusions=company_exclusions,
        )
        for name in sorted(profiles)
        if profiles[name].get("enabled", False)
    )
