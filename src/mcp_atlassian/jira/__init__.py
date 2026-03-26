"""Jira API module for mcp_atlassian.

This module provides various Jira API client implementations.
"""

# flake8: noqa

# Re-export the Jira class for backward compatibility
from atlassian.jira import Jira

from .client import JiraClient
from .config import JiraConfig
from .projects import ProjectsMixin
from .search import SearchMixin
from .issues import IssuesMixin
from .fields import FieldsMixin
from .users import UsersMixin
from .epics import EpicsMixin
from .attachments import AttachmentsMixin
from .transitions import TransitionsMixin


class JiraFetcher(
    ProjectsMixin,
    SearchMixin,
    IssuesMixin,
    FieldsMixin,
    UsersMixin,
    EpicsMixin,
    AttachmentsMixin,
    TransitionsMixin,
):
    """
    The main Jira client class providing access to all Jira operations.

    This class inherits from multiple mixins that provide specific functionality:
    - ProjectsMixin: Project-related operations
    - FieldsMixin: Field-related operations
    - FormattingMixin: Content formatting utilities
    - TransitionsMixin: Issue transition operations
    - WorklogMixin: Worklog operations
    - EpicsMixin: Epic operations
    - CommentsMixin: Comment operations
    - SearchMixin: Search operations
    - IssuesMixin: Issue operations
    - UsersMixin: User operations
    - BoardsMixin: Board operations
    - SprintsMixin: Sprint operations
    - AttachmentsMixin: Attachment download operations
    - LinksMixin: Issue link operations

    The class structure is designed to maintain backward compatibility while
    improving code organization and maintainability.
    """

    pass


__all__ = ["JiraFetcher", "JiraConfig", "JiraClient", "Jira"]
