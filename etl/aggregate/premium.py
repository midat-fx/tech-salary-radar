"""How much more a posting pays when it asks for a skill.

The site's flagship number, and the one most easily got wrong. Three rules make
it mean something:

**Stratify.** Compare within a level and a region, never across. Kubernetes
looks like a fifty per cent premium if senior American postings mention it more
than junior European ones — that is the level and the country talking, not the
skill. See ADR 0004.

**Only postings that were read.** A posting the model never labelled is not
evidence the skill is absent, and putting it in the without-pool deflated every
premium on the site until it was found. See ADR 0003.

**Report the interval.** A skill that appears in fifteen postings can show a
large premium by luck. The bootstrap interval is what makes that visible instead
of publishing the point estimate alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from etl.aggregate.bootstrap import MIN_STRATUM, bootstrap_interval, weighted_premium
from etl.aggregate.labels import labels_for
from etl.rng import bootstrap_rng

__all__ = ["SkillPremium", "MIN_TOTAL_WITH", "TOP_N", "skill_premiums", "build_strata"]

#: A skill needs this many salary-bearing postings overall before it is shown.
#: Below it the premium is a handful of people's pay.
MIN_TOTAL_WITH = 15

#: How many skills reach the page. The tail is long and thin, and a list of
#: sixty entries invites reading rank 40 against rank 41.
TOP_N = 10

_SALARY_ROWS = """
    SELECT s.job_uid, s.seniority, s.region, s.salary_mid_usd
    FROM snap s
    WHERE s.snapshot_date = ? AND s.has_salary AND NOT s.is_management
          AND s.salary_mid_usd IS NOT NULL
"""


@dataclass(frozen=True)
class SkillPremium:
    """One published row: the skill, its premium, and how much to trust it."""

    skill: str
    n: int
    premium_pct: float
    median_with_usd: int
    ci_lo: float | None
    ci_hi: float | None

    @property
    def is_significant(self) -> bool:
        """True when the interval stays above zero — the premium is not noise."""
        return self.ci_lo is not None and self.ci_lo > 0

    def as_dict(self) -> dict:
        return {
            "skill": self.skill,
            "n": self.n,
            "premium_pct": self.premium_pct,
            "median_with_usd": self.median_with_usd,
            "ci_lo": self.ci_lo,
            "ci_hi": self.ci_hi,
        }


def build_strata(rows, index) -> tuple[dict[tuple[str, str], list], set[str]]:
    """Group read postings by (seniority, region) and collect the skills seen."""
    strata: dict[tuple[str, str], list[tuple[float, set[str]]]] = {}
    skills_seen: set[str] = set()
    for uid, seniority, region, salary in rows:
        if not index.was_read(uid):
            continue
        skills = index.skills(uid)
        skills_seen |= skills
        strata.setdefault((seniority, region), []).append((salary, skills))
    return strata, skills_seen


def skill_premiums(con, latest_date, rng=None, top_n: int = TOP_N) -> list[SkillPremium]:
    """Every skill worth publishing for one day, best premium first."""
    rows = con.execute(_SALARY_ROWS, [latest_date]).fetchall()
    if not rows:
        return []
    index = labels_for(con, [row[0] for row in rows])
    strata, skills_seen = build_strata(rows, index)

    rng = rng or bootstrap_rng()
    results: list[SkillPremium] = []
    for skill in sorted(skills_seen):
        pools: list[tuple[list[float], list[float]]] = []
        with_pool: list[float] = []
        total_with = 0
        for members in strata.values():
            has = [salary for salary, skills in members if skill in skills]
            has_not = [salary for salary, skills in members if skill not in skills]
            total_with += len(has)
            if len(has) >= MIN_STRATUM and len(has_not) >= MIN_STRATUM:
                pools.append((has, has_not))
                with_pool += has
        if total_with < MIN_TOTAL_WITH or not pools:
            continue
        premium = weighted_premium(pools)
        if premium is None or premium <= 0:
            continue
        low, high = bootstrap_interval(pools, rng)
        results.append(
            SkillPremium(
                skill=skill,
                n=len(with_pool),
                premium_pct=round(premium, 1),
                median_with_usd=round(median(with_pool)),
                ci_lo=low,
                ci_hi=high,
            )
        )
    results.sort(key=lambda r: r.premium_pct, reverse=True)
    return results[:top_n]
