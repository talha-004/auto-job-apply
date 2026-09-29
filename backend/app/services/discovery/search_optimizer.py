"""
SearchOptimizerService — Search Intelligence, Query Expansion, and Relevancy Gating.
Expands search queries into high-yield industry synonyms, constructs platform-specific
boolean search expressions and URLs, applies pre-scrape title relevance filtering,
and collects search yield telemetry.
"""

import re
import uuid
import urllib.parse
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Set
from pydantic import BaseModel, Field

from app.core.logger import logger


class SearchTelemetry(BaseModel):
    search_id: str = Field(default_factory=lambda: f"srch_{uuid.uuid4().hex[:8]}")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    base_query: str
    expanded_queries: List[str] = Field(default_factory=list)
    location: str = ""
    total_scraped: int = 0
    relevance_filtered: int = 0
    duplicates_skipped: int = 0
    fresh_eligible: int = 0
    yield_rate_pct: float = 0.0


class SearchOptimizerService:
    """
    Search intelligence service providing:
      1. Synonym & query expansion across engineering, data, AI, and design roles.
      2. Boolean query generator tailored for job boards.
      3. Deep platform URL construction with precise date and remote filters.
      4. Fast-path title relevance and negative keyword filtering.
      5. Search yield telemetry tracking.
    """

    DEFAULT_NEGATIVE_KEYWORDS = [
        "intern", "internship", "director", "vp", "vice president",
        "unpaid", "volunteer", "trainee"
    ]

    # Pre-compiled common stop words for title relevance calculation
    STOP_WORDS = {
        "and", "or", "the", "a", "an", "in", "at", "for", "with", "of", "to",
        "on", "by", "as", "is", "senior", "junior", "lead", "staff", "principal"
    }

    ROLE_SYNONYMS: Dict[str, List[str]] = {
        "python developer": [
            "Python Engineer",
            "Backend Engineer Python",
            "Python Software Engineer",
            "FastAPI Developer",
            "Django Developer"
        ],
        "backend developer": [
            "Backend Engineer",
            "Software Engineer - Backend",
            "Server-Side Developer",
            "Python Backend Engineer",
            "API Developer"
        ],
        "frontend developer": [
            "Frontend Engineer",
            "React Developer",
            "UI Developer",
            "Web Developer",
            "React.js Engineer"
        ],
        "full stack developer": [
            "Full Stack Engineer",
            "Fullstack Software Engineer",
            "Python Full Stack Developer",
            "Web Application Engineer"
        ],
        "data engineer": [
            "Data Platform Engineer",
            "ETL Developer",
            "Big Data Engineer",
            "Python Data Engineer",
            "Analytics Engineer"
        ],
        "machine learning engineer": [
            "ML Engineer",
            "AI Engineer",
            "Machine Learning Scientist",
            "Data Scientist / ML"
        ],
        "devops engineer": [
            "Site Reliability Engineer",
            "SRE",
            "Cloud Engineer",
            "Platform Engineer",
            "Infrastructure Engineer"
        ],
        "software engineer": [
            "Software Developer",
            "Backend Software Engineer",
            "Full Stack Software Engineer",
            "Application Developer"
        ]
    }

    def __init__(self):
        self.telemetry_history: List[SearchTelemetry] = []

    def expand_queries(self, keywords: str, max_variations: int = 3) -> List[str]:
        """
        Expands a user-provided search term into high-yield industry role synonyms.
        Guarantees the original query is always the primary (first) element.
        """
        normalized = keywords.lower().strip()
        expanded: List[str] = [keywords.strip()]

        # 1. Exact or partial match in dictionary
        matched_synonyms: List[str] = []
        for role_key, syns in self.ROLE_SYNONYMS.items():
            if role_key in normalized or normalized in role_key:
                matched_synonyms.extend(syns)

        # 2. If no direct match, generate heuristic variations
        if not matched_synonyms:
            tokens = [t.capitalize() for t in normalized.split() if t not in self.STOP_WORDS]
            base = " ".join(tokens)
            if "developer" in normalized:
                matched_synonyms.append(f"{base.replace('Developer', 'Engineer').strip()}")
                matched_synonyms.append(f"Software {base}")
            elif "engineer" in normalized:
                matched_synonyms.append(f"{base.replace('Engineer', 'Developer').strip()}")
                matched_synonyms.append(f"Senior {base}")
            else:
                matched_synonyms.append(f"{base} Engineer")
                matched_synonyms.append(f"{base} Developer")

        # Deduplicate while preserving order
        seen = {keywords.strip().lower()}
        for syn in matched_synonyms:
            syn_clean = syn.strip()
            if syn_clean.lower() not in seen and len(expanded) <= max_variations:
                seen.add(syn_clean.lower())
                expanded.append(syn_clean)

        return expanded

    def build_boolean_search(
        self,
        keywords: str,
        negative_keywords: Optional[List[str]] = None,
        required_skills: Optional[List[str]] = None
    ) -> str:
        """
        Constructs a boolean search query string supported by major job platforms.
        E.g.: ("Python Developer" OR "Python Engineer") AND ("FastAPI" OR "Django") NOT ("Intern" OR "Unpaid")
        """
        expansions = self.expand_queries(keywords, max_variations=2)
        quoted_titles = [f'"{q}"' if " " in q else q for q in expansions]
        title_clause = f"({' OR '.join(quoted_titles)})"

        parts = [title_clause]

        if required_skills:
            clean_skills = [f'"{s.strip()}"' if " " in s.strip() else s.strip() for s in required_skills if s.strip()]
            if clean_skills:
                parts.append(f"({' OR '.join(clean_skills)})")

        negatives = (negative_keywords or []) + self.DEFAULT_NEGATIVE_KEYWORDS
        negatives = list(dict.fromkeys([n.strip().capitalize() for n in negatives if n.strip()]))
        if negatives:
            quoted_neg = [f'"{n}"' if " " in n else n for n in negatives[:6]]
            parts.append(f"NOT ({' OR '.join(quoted_neg)})")

        return " AND ".join(parts)

    def build_platform_search_url(
        self,
        platform: str,
        keywords: str,
        location: str,
        is_remote: bool = False,
        hours_old: int = 72,
        experience_level: Optional[str] = None
    ) -> str:
        """
        Constructs an exact URL with URL query parameters for target job boards.
        """
        encoded_kw = urllib.parse.quote_plus(keywords)
        encoded_loc = urllib.parse.quote_plus(location)
        plat = platform.lower().strip()

        if "linkedin" in plat:
            # f_TPR: r86400 (24h), r604800 (week), etc.
            seconds = max(3600, hours_old * 3600)
            url = f"https://www.linkedin.com/jobs/search/?keywords={encoded_kw}&location={encoded_loc}&f_TPR=r{seconds}"
            if is_remote:
                url += "&f_WT=2"  # 2 = Remote on LinkedIn
            if experience_level:
                exp_map = {"entry": "2", "mid": "3,4", "senior": "4,5"}
                if experience_level.lower() in exp_map:
                    url += f"&f_E={exp_map[experience_level.lower()]}"
            return url

        elif "indeed" in plat:
            days = max(1, hours_old // 24)
            url = f"https://www.indeed.com/jobs?q={encoded_kw}&l={encoded_loc}&fromage={days}"
            if is_remote:
                url += "&sc=0kf%3Aattr%28DSIDE%29%3B"
            return url

        elif "naukri" in plat:
            kw_slug = re.sub(r"[^a-zA-Z0-9]+", "-", keywords.lower()).strip("-")
            loc_slug = re.sub(r"[^a-zA-Z0-9]+", "-", location.lower()).strip("-")
            days = max(1, hours_old // 24)
            url = f"https://www.naukri.com/{kw_slug}-jobs-in-{loc_slug}?glbl_qc_job_age={days}"
            if is_remote:
                url += "&wfhType=0"
            return url

        # Fallback generic query
        return f"https://www.google.com/search?q={encoded_kw}+jobs+in+{encoded_loc}"

    def filter_title_relevance(
        self,
        title: str,
        target_query: str,
        negative_keywords: Optional[List[str]] = None
    ) -> Tuple[bool, str]:
        """
        High-speed pre-filter validating title relevance before expensive scraping.
        Returns: (is_relevant: bool, reason: str)
        """
        norm_title = title.lower().strip()
        norm_query = target_query.lower().strip()

        # 1. Negative keyword check
        all_negatives = (negative_keywords or []) + self.DEFAULT_NEGATIVE_KEYWORDS
        for neg in all_negatives:
            if not neg:
                continue
            pattern = rf"\b{re.escape(neg.lower())}\b"
            if re.search(pattern, norm_title):
                return False, f"Title contains negative keyword '{neg}'."

        # 2. Token overlap check between title and target query
        query_tokens = set(re.findall(r"\b[a-zA-Z]{3,}\b", norm_query)) - self.STOP_WORDS
        title_tokens = set(re.findall(r"\b[a-zA-Z]{3,}\b", norm_title)) - self.STOP_WORDS

        if not query_tokens:
            return True, "No semantic query tokens to validate; accepted."

        # Compute token overlap
        overlap = query_tokens.intersection(title_tokens)
        if overlap:
            return True, f"Relevant (matched tokens: {', '.join(overlap)})"

        # Check common technology stems (e.g. py, js, react, java, node)
        for qt in query_tokens:
            for tt in title_tokens:
                if qt in tt or tt in qt:
                    return True, f"Relevant (sub-token match: {qt} ~ {tt})"

        return False, f"Title '{title}' has zero semantic overlap with search target '{target_query}'."

    def record_telemetry(
        self,
        base_query: str,
        expanded_queries: List[str],
        location: str,
        total_scraped: int,
        relevance_filtered: int,
        duplicates_skipped: int,
        fresh_eligible: int
    ) -> SearchTelemetry:
        """Calculates yield rate and stores search run telemetry."""
        yield_rate = (fresh_eligible / total_scraped * 100.0) if total_scraped > 0 else 0.0

        telemetry = SearchTelemetry(
            base_query=base_query,
            expanded_queries=expanded_queries,
            location=location,
            total_scraped=total_scraped,
            relevance_filtered=relevance_filtered,
            duplicates_skipped=duplicates_skipped,
            fresh_eligible=fresh_eligible,
            yield_rate_pct=round(yield_rate, 1)
        )

        self.telemetry_history.append(telemetry)
        logger.info(
            f"[SearchOptimizer] Telemetry for '{base_query}': {total_scraped} raw scraped -> "
            f"{relevance_filtered} filtered, {duplicates_skipped} duplicates -> {fresh_eligible} fresh ({telemetry.yield_rate_pct}% yield)"
        )
        return telemetry

    def get_recent_telemetry(self, limit: int = 10) -> List[SearchTelemetry]:
        return self.telemetry_history[-limit:]

    def clear(self):
        self.telemetry_history.clear()


search_optimizer = SearchOptimizerService()
