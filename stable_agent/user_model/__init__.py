"""User model layer for the Recursive Harness.

This package keeps personalization as explicit, reviewable data:
expression habits, cognitive preferences, temperament policy, and feedback
candidates. Nothing here auto-promotes high-risk preferences.
"""

from stable_agent.user_model.cognitive_profile import default_cognitive_profile
from stable_agent.user_model.expression_profile import default_expression_profile
from stable_agent.user_model.feedback_parser import FeedbackParser
from stable_agent.user_model.models import (
    CognitiveProfile,
    ExpressionProfile,
    PreferenceCandidate,
    TemperamentPolicy,
)
from stable_agent.user_model.repository import UserModelRepository
from stable_agent.user_model.temperament_policy import default_temperament_policy

__all__ = [
    "CognitiveProfile",
    "ExpressionProfile",
    "FeedbackParser",
    "PreferenceCandidate",
    "TemperamentPolicy",
    "UserModelRepository",
    "default_cognitive_profile",
    "default_expression_profile",
    "default_temperament_policy",
]
