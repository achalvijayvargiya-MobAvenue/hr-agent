"""
Service for intelligently merging Zoho form data with LLM-extracted resume data.
"""

import logging
from dataclasses import dataclass, field, asdict
from enum import StrEnum
from typing import Any, Optional

from hr_agent.schemas.candidate import CVExtracted

logger = logging.getLogger(__name__)


class MergeStrategy(StrEnum):
    """Strategy for resolving field conflicts."""
    
    STANDARD = "standard"  # Zoho for structured, resume for rich fields
    RESUME_PRIORITY = "resume_priority"  # Resume takes precedence
    ZOHO_PRIORITY = "zoho_priority"  # Zoho takes precedence


@dataclass
class ZohoFormData:
    """Structured data extracted from Zoho form submission."""
    
    name: Optional[str] = None
    email: Optional[str] = None
    current_title: Optional[str] = None
    current_company: Optional[str] = None
    location: Optional[str] = None
    skills: list[str] = field(default_factory=list)
    years_experience: Optional[int] = None
    seniority_level: Optional[str] = None
    certifications: list[str] = field(default_factory=list)
    industries: list[str] = field(default_factory=list)
    summary: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, filtering out None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class MergedCandidateData:
    """Result of merging Zoho form data + resume extraction."""
    
    # Core fields
    name: Optional[str] = None
    email: Optional[str] = None
    current_title: Optional[str] = None
    normalized_role: Optional[str] = None
    years_experience: Optional[float] = None
    current_company: Optional[str] = None
    location: Optional[str] = None
    
    # Lists
    skills: list[str] = field(default_factory=list)
    tools_and_technologies: list[str] = field(default_factory=list)
    education: list[dict] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    employment_history: list[dict] = field(default_factory=list)
    industries: list[str] = field(default_factory=list)
    experience_areas: list[str] = field(default_factory=list)
    responsibilities: list[str] = field(default_factory=list)
    
    # Metadata
    seniority_level: Optional[str] = None
    summary: Optional[str] = None
    
    # Data source tracking: field_name → ["zoho", "resume"]
    data_sources: dict[str, list[str]] = field(default_factory=dict)
    
    def get_field_sources(self, field_name: str) -> list[str]:
        """Which sources provided this field's value."""
        return self.data_sources.get(field_name, [])
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        d = asdict(self)
        # Remove None values for cleaner output
        return {k: v for k, v in d.items() if v not in (None, [], {})}


class CandidateMergeService:
    """Intelligently merge Zoho form data with resume extraction."""
    
    # Field merge preferences
    MERGE_PREFERENCES = {
        # ZOHO_PRIORITY: Use Zoho first, fallback to resume
        "zoho_priority": [
            "name",
            "current_title",
            "current_company",
            "location",
            "seniority_level",
            "years_experience",
        ],
        # RESUME_PRIORITY: Use resume first
        "resume_priority": [
            "normalized_role",
            "education",
            "employment_history",
            "tools_and_technologies",
            "experience_areas",
            "responsibilities",
        ],
        # UNION: Combine both (remove duplicates)
        "union": [
            "skills",
            "certifications",
            "industries",
        ],
        # RESUME_ONLY: Ignore Zoho, use resume
        "resume_only": [
            "education",
            "employment_history",
            "tools_and_technologies",
            "experience_areas",
            "responsibilities",
        ],
    }
    
    def merge_sources(
        self,
        zoho_data: ZohoFormData,
        extracted: CVExtracted,
        merge_strategy: MergeStrategy = MergeStrategy.STANDARD,
    ) -> MergedCandidateData:
        """
        Merge two data sources according to strategy.
        
        Args:
            zoho_data: Structured form data from Zoho
            extracted: Extracted data from resume via LLM
            merge_strategy: How to handle field conflicts
        
        Returns:
            MergedCandidateData with all fields + source tracking
        """
        logger.info(
            f"[MERGE] Starting merge — strategy={merge_strategy} "
            f"zoho_email={zoho_data.email} resume_email={extracted.email}"
        )
        
        merged = MergedCandidateData()
        
        # Email: Use from resume (primary key), fallback to Zoho
        merged.email, sources = self._merge_email(zoho_data.email, extracted.email)
        merged.data_sources["email"] = sources
        
        # Name: Prefer Zoho (more likely to be correct in form)
        merged.name, sources = self._merge_field_string(
            "name",
            zoho_data.name,
            extracted.candidate_name,
            merge_strategy,
        )
        merged.data_sources["name"] = sources
        
        # Current title: Prefer Zoho
        merged.current_title, sources = self._merge_field_string(
            "current_title",
            zoho_data.current_title,
            extracted.current_title,
            merge_strategy,
        )
        merged.data_sources["current_title"] = sources
        
        # Current company: Prefer Zoho
        merged.current_company, sources = self._merge_field_string(
            "current_company",
            zoho_data.current_company,
            extracted.current_company,
            merge_strategy,
        )
        merged.data_sources["current_company"] = sources
        
        # Location: Merge (use Zoho as primary)
        merged.location, sources = self._merge_field_string(
            "location",
            zoho_data.location,
            extracted.location,
            merge_strategy,
        )
        merged.data_sources["location"] = sources
        
        # Years experience: Prefer Zoho (if numeric)
        merged.years_experience, sources = self._merge_field_numeric(
            "years_experience",
            zoho_data.years_experience,
            extracted.years_experience,
            merge_strategy,
        )
        merged.data_sources["years_experience"] = sources
        
        # Seniority level: Prefer Zoho
        merged.seniority_level, sources = self._merge_field_string(
            "seniority_level",
            zoho_data.seniority_level,
            extracted.seniority_level,
            merge_strategy,
        )
        merged.data_sources["seniority_level"] = sources
        
        # Skills: Union strategy (combine both)
        merged.skills, sources = self._merge_field_list(
            "skills",
            zoho_data.skills,
            extracted.skills,
            "union",
        )
        merged.data_sources["skills"] = sources
        
        # Certifications: Union
        merged.certifications, sources = self._merge_field_list(
            "certifications",
            zoho_data.certifications,
            extracted.certifications,
            "union",
        )
        merged.data_sources["certifications"] = sources
        
        # Industries: Union
        merged.industries, sources = self._merge_field_list(
            "industries",
            zoho_data.industries,
            extracted.industries,
            "union",
        )
        merged.data_sources["industries"] = sources
        
        # Resume-only fields (always from extracted)
        merged.normalized_role = extracted.normalized_role
        merged.education = [e.model_dump() for e in extracted.education]
        merged.employment_history = [e.model_dump() for e in extracted.employment_history]
        merged.tools_and_technologies = extracted.tools_and_technologies
        merged.experience_areas = extracted.experience_areas
        merged.responsibilities = extracted.responsibilities
        
        merged.data_sources["normalized_role"] = ["resume"]
        merged.data_sources["education"] = ["resume"]
        merged.data_sources["employment_history"] = ["resume"]
        merged.data_sources["tools_and_technologies"] = ["resume"]
        merged.data_sources["experience_areas"] = ["resume"]
        merged.data_sources["responsibilities"] = ["resume"]
        
        # Summary: Prefer resume (usually more detailed)
        merged.summary, sources = self._merge_field_string(
            "summary",
            zoho_data.summary,
            extracted.summary,
            "resume_priority",
        )
        merged.data_sources["summary"] = sources
        
        logger.info(
            f"[MERGE] Merge complete ✓ — name={merged.name!r} email={merged.email!r} "
            f"skills_count={len(merged.skills)} sources_tracked={len(merged.data_sources)}"
        )
        
        return merged
    
    def _merge_email(
        self, zoho_email: Optional[str], resume_email: Optional[str]
    ) -> tuple[Optional[str], list[str]]:
        """Merge email: use from resume (primary key), fallback to Zoho."""
        if resume_email:
            return resume_email, ["resume"]
        return zoho_email, ["zoho"] if zoho_email else []
    
    def _merge_field_string(
        self,
        field_name: str,
        zoho_value: Optional[str],
        resume_value: Optional[str],
        strategy: MergeStrategy,
    ) -> tuple[Optional[str], list[str]]:
        """
        Merge a string field.
        
        Returns: (merged_value, sources)
        """
        # Normalize empty strings to None
        zoho_val = zoho_value.strip() if zoho_value else None
        resume_val = resume_value.strip() if resume_value else None
        
        # Both present: choose based on strategy
        if zoho_val and resume_val:
            if strategy == MergeStrategy.RESUME_PRIORITY:
                logger.debug(
                    f"[MERGE] Conflict on {field_name}: "
                    f"choosing resume='{resume_val}' over zoho='{zoho_val}'"
                )
                return resume_val, ["resume"]
            elif strategy == MergeStrategy.ZOHO_PRIORITY:
                logger.debug(
                    f"[MERGE] Conflict on {field_name}: "
                    f"choosing zoho='{zoho_val}' over resume='{resume_val}'"
                )
                return zoho_val, ["zoho"]
            else:  # STANDARD: prefer Zoho for structured fields
                return zoho_val, ["zoho"]
        
        # Only one present
        if zoho_val:
            return zoho_val, ["zoho"]
        if resume_val:
            return resume_val, ["resume"]
        
        return None, []
    
    def _merge_field_numeric(
        self,
        field_name: str,
        zoho_value: Optional[int],
        resume_value: Optional[float],
        strategy: MergeStrategy,
    ) -> tuple[Optional[float], list[str]]:
        """Merge a numeric field (years of experience)."""
        # Both present: prefer Zoho (usually more accurate in form)
        if zoho_value is not None and resume_value is not None:
            if strategy == MergeStrategy.RESUME_PRIORITY:
                return resume_value, ["resume"]
            else:
                # STANDARD or ZOHO_PRIORITY: use Zoho
                return float(zoho_value), ["zoho"]
        
        if zoho_value is not None:
            return float(zoho_value), ["zoho"]
        if resume_value is not None:
            return resume_value, ["resume"]
        
        return None, []
    
    def _merge_field_list(
        self,
        field_name: str,
        zoho_values: list[str],
        resume_values: list[str],
        merge_mode: str = "union",
    ) -> tuple[list[str], list[str]]:
        """
        Merge a list field.
        
        Args:
            merge_mode: "union" (combine), "resume_priority", "zoho_priority"
        
        Returns: (merged_list, sources)
        """
        zoho_clean = [v.strip().lower() for v in zoho_values if v and v.strip()]
        resume_clean = [v.strip().lower() for v in resume_values if v and v.strip()]
        
        if merge_mode == "union":
            # Combine and deduplicate
            combined = list(set(zoho_clean + resume_clean))
            sources = []
            if zoho_clean:
                sources.append("zoho")
            if resume_clean:
                sources.append("resume")
            
            logger.debug(
                f"[MERGE] Union on {field_name}: "
                f"zoho_count={len(zoho_clean)} resume_count={len(resume_clean)} "
                f"merged_count={len(combined)}"
            )
            
            return sorted(combined), sources
        
        elif merge_mode == "resume_priority":
            if resume_values:
                return resume_clean, ["resume"]
            return zoho_clean, ["zoho"] if zoho_clean else []
        
        else:  # ZOHO_PRIORITY
            if zoho_values:
                return zoho_clean, ["zoho"]
            return resume_clean, ["resume"] if resume_clean else []
