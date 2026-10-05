import unittest

from job_engine.ats import NormalizedPosting
from job_engine.matching import match_enabled_profiles, match_profile


def posting(**overrides):
    values = {
        "source_name": "fixture",
        "source_job_id": "job-1",
        "title": "Python Automation Developer",
        "company": "Example Ltd",
        "source_url": "https://example.invalid/jobs/1",
        "description": "Build tested Python automation tools.",
        "location": "Manchester, GB",
        "employment_type": "full_time",
        "remote_mode": "hybrid",
        "metadata": {"salary_gbp": "42000"},
    }
    values.update(overrides)
    return NormalizedPosting(**values)


PROFILE = {
    "enabled": True,
    "employment_types": ["full_time"],
    "keywords": {"include": ["Python"], "exclude": ["senior"]},
    "locations": {"include": ["Manchester"]},
    "remote": {"modes": ["hybrid"]},
    "salary": {"minimum_gbp": 40000},
    "score_threshold": 70,
}


class MatchingTests(unittest.TestCase):
    def test_matching_profile_is_explainable(self):
        decision = match_profile(posting(), "full_time", PROFILE)
        self.assertTrue(decision.matched)
        self.assertEqual(decision.score, 80)
        self.assertIn("include_keywords:python", decision.reasons)

    def test_excluded_keyword_blocks_match(self):
        decision = match_profile(
            posting(title="Senior Python Automation Developer"),
            "full_time",
            PROFILE,
        )
        self.assertTrue(decision.excluded)
        self.assertFalse(decision.matched)
        self.assertIn("excluded_keywords:senior", decision.reasons)

    def test_clearance_wording_is_excluded_before_scoring(self):
        decision = match_profile(
            posting(description="This role requires SC clearance."),
            "full_time",
            PROFILE,
        )
        self.assertTrue(decision.excluded)
        self.assertFalse(decision.matched)
        self.assertEqual(decision.score, 0)
        self.assertEqual(decision.reasons, ("clearance_exclusion:sc clearance",))

    def test_security_check_and_structured_clearance_are_excluded(self):
        security_check = match_profile(
            posting(description="Security Check required for this role."),
            "full_time",
            PROFILE,
        )
        structured = match_profile(
            posting(
                description="Build Python automation tools.",
                clearance_requirements=("SC",),
            ),
            "full_time",
            PROFILE,
        )
        self.assertTrue(security_check.excluded)
        self.assertTrue(structured.excluded)

    def test_clearance_terms_can_be_configured(self):
        decision = match_profile(
            posting(description="DV clearance required."),
            "full_time",
            PROFILE,
            clearance_exclusions=("DV",),
        )
        self.assertTrue(decision.excluded)
        self.assertIn("clearance_exclusion:dv", decision.reasons)

    def test_company_name_alias_and_domain_exclusions_are_applied_before_scoring(self):
        exclusions = (
            {
                "name": "Blocked Holdings",
                "aliases": ["Blocked Ltd"],
                "domains": ["blocked.example"],
                "reason": "Existing application conflict",
            },
        )
        alias_decision = match_profile(
            posting(company="Blocked Ltd"),
            "full_time",
            PROFILE,
            company_exclusions=exclusions,
        )
        domain_decision = match_profile(
            posting(
                company="Other Company",
                source_url="https://www.blocked.example/jobs/1",
            ),
            "full_time",
            PROFILE,
            company_exclusions=exclusions,
        )
        self.assertTrue(alias_decision.excluded)
        self.assertEqual(
            alias_decision.reasons,
            ("company_exclusion:Existing application conflict",),
        )
        self.assertTrue(domain_decision.excluded)

    def test_unconfigured_company_is_not_excluded(self):
        decision = match_profile(posting(), "full_time", PROFILE)
        self.assertFalse(decision.excluded)

    def test_incompatible_remote_country_is_excluded_before_scoring(self):
        profile = {
            **PROFILE,
            "remote": {
                "modes": ["hybrid"],
                "allowed_countries": ["GB"],
                "worldwide": False,
            },
        }
        decision = match_profile(
            posting(
                location="New York, US",
                metadata={"salary_gbp": "42000", "work_countries": "US"},
            ),
            "full_time",
            profile,
        )
        self.assertTrue(decision.excluded)
        self.assertEqual(decision.score, 0)
        self.assertIn("work_country_incompatible", decision.reasons)

    def test_remote_unknowns_are_explicit(self):
        profile = {
            **PROFILE,
            "remote": {
                "modes": ["hybrid"],
                "allowed_countries": ["GB"],
                "worldwide": False,
                "timezones": ["Europe/London"],
            },
        }
        decision = match_profile(
            posting(location=None, metadata={"salary_gbp": "42000"}),
            "full_time",
            profile,
        )
        self.assertIn("work_country_missing", decision.unknowns)
        self.assertIn("right_to_work_countries_missing", decision.unknowns)
        self.assertIn("tax_countries_missing", decision.unknowns)
        self.assertIn("timezone_missing", decision.unknowns)

    def test_worldwide_remote_role_does_not_require_country_overlap(self):
        profile = {
            **PROFILE,
            "remote": {
                "modes": ["hybrid"],
                "allowed_countries": ["GB"],
                "worldwide": True,
            },
            "locations": {"include": []},
        }
        decision = match_profile(
            posting(
                location="Toronto, CA",
                metadata={"salary_gbp": "42000", "work_countries": "CA"},
            ),
            "full_time",
            profile,
        )
        self.assertFalse(decision.excluded)

    def test_missing_optional_values_are_unknown(self):
        decision = match_profile(
            posting(location=None, remote_mode=None, metadata={}),
            "full_time",
            PROFILE,
        )
        self.assertFalse(decision.matched)
        self.assertIn("salary_missing", decision.unknowns)
        self.assertIn("location_missing", decision.unknowns)

    def test_mismatched_employment_type_is_excluded(self):
        decision = match_profile(
            posting(employment_type="part_time"),
            "full_time",
            PROFILE,
        )
        self.assertTrue(decision.excluded)
        self.assertIn("employment_type_mismatch", decision.reasons)

    def test_enabled_profiles_are_sorted_and_disabled_profiles_omitted(self):
        decisions = match_enabled_profiles(
            posting(),
            {
                "z_profile": PROFILE,
                "a_profile": PROFILE,
                "disabled": {**PROFILE, "enabled": False},
            },
        )
        self.assertEqual(
            tuple(decision.profile_name for decision in decisions),
            ("a_profile", "z_profile"),
        )
