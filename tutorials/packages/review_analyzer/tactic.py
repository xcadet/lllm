"""
ReviewAnalyzerTactic — example multi-agent tactic shipped as a package.

Usage:
    from tutorials.packages.review_analyzer.tactic import ReviewAnalyzerTactic
    result = ReviewAnalyzerTactic().run(reviews=["Great product!", "Battery dies fast."])
"""

from __future__ import annotations
from typing import Any
import lllm


class ReviewAnalyzerTactic(lllm.Tactic):
    """Pipeline: analyzer -> summarizer."""

    def setup(self) -> None:
        self.analyzer = lllm.Agent(
            model="gpt-4o-mini",
            system=(
                "You are a product review analyst. Identify sentiment (positive/neutral/negative), "
                "list up to 3 pros and 3 cons, and flag any defects or safety concerns. "
                "Be concise and factual."
            ),
        )
        self.summarizer = lllm.Agent(
            model="gpt-4o-mini",
            system=(
                "You are a report writer. Given a review analysis, produce a 3-5 sentence "
                "executive summary with actionable insights for a product manager."
            ),
        )

    def run(self, reviews: list[str]) -> dict[str, Any]:  # type: ignore[override]
        combined = "\n---\n".join(reviews)
        analysis = self.analyzer.call(f"Analyze these reviews:\n\n{combined}")
        summary = self.summarizer.call(f"Summarize this analysis:\n\n{analysis}")
        return {"analysis": analysis, "summary": summary}
