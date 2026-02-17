"""User preference profile storage and interview flow."""

from .profile import default_user_profile, summarize_profile
from .store import PreferencesStore

__all__ = ["PreferencesStore", "default_user_profile", "run_interview", "summarize_profile"]


def run_interview(*args, **kwargs):
    from .interview import run_interview as _run_interview

    return _run_interview(*args, **kwargs)
