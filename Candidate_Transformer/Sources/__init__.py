"""Source adapters: one per input type.

Each adapter discovers its files inside the inputs directory and yields
``SourceRecord`` objects (one per person). Adapters never raise on bad input —
they log a warning and yield nothing, so a single garbage source cannot crash
the run.
"""

from .recruiter_csv import RecruiterCsvAdapter
from .ats_json import AtsJsonAdapter
from .resume import ResumeAdapter
from .github import GithubAdapter

# Order here is irrelevant to merge priority (that lives in confidence.py); it
# is just the discovery order.
ALL_ADAPTERS = [
    RecruiterCsvAdapter(),
    AtsJsonAdapter(),
    ResumeAdapter(),
    GithubAdapter(),
]

__all__ = [
    "RecruiterCsvAdapter",
    "AtsJsonAdapter",
    "ResumeAdapter",
    "GithubAdapter",
    "ALL_ADAPTERS",
]
