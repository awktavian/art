"""Complete Action Space — THE Source of Truth for All Actions.

This module defines THE COMPLETE action space for Kagami's motor decoder
and sensory integration. It categorizes ALL tools from ALL integrations
into their proper Markov blanket roles:

    SENSORS (η → s): Actions that READ/QUERY the environment
    EFFECTORS (a → η): Actions that WRITE/MODIFY the environment

Architecture:
    ┌──────────────────────────────────────────────────────────────────┐
    │                      MARKOV BLANKET                              │
    ├────────────────────────────┬─────────────────────────────────────┤
    │  SENSORS (η → s)           │  EFFECTORS (a → η)                  │
    │  ─────────────────         │  ──────────────────                 │
    │  Composio READ (241)       │  Composio WRITE (259)               │
    │  SmartHome GET (55)        │  SmartHome SET (78)                 │
    │  Builtin READ (22)         │  Builtin WRITE (21)                 │
    │  Desktop READ (13)         │  Desktop WRITE (20)                 │
    │  Generation READ (4)       │  Generation WRITE (15)              │
    │                            │  Meta Control (7)                   │
    │  ─────────────────         │  ──────────────────                 │
    │  Total: 334                │  Total: 388                         │
    └──────────────────────────────────────────────────────────────────┘

    GRAND TOTAL: 722 actions

AUTOMATIC WORLD MODEL COUPLING (Dec 30, 2025):
=============================================
The ActionSpaceRegistry provides automatic synchronization between the action
space and the world model to prevent drift. Any new actions registered at
runtime are automatically reflected in the world model's action embedding space.

Usage:
    from kagami.core.embodiment.action_space import get_action_registry

    registry = get_action_registry()
    registry.register_action("new_action", ActionRole.EFFECTOR, ActionDomain.DIGITAL)
    registry.sync_to_world_model()  # Automatic: extends world model action space

Auto-generated from live Composio API. Last updated: 2025-12-30
Run `python -m kagami.core.embodiment.action_space` to regenerate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# =============================================================================
# MARKOV BLANKET CLASSIFICATION
# =============================================================================


class ActionRole(Enum):
    """Role of an action in the Markov blanket."""

    SENSOR = "sensor"  # η → s: Reads from environment
    EFFECTOR = "effector"  # a → η: Writes to environment


class ActionDomain(Enum):
    """Domain of the action."""

    DIGITAL = "digital"  # Composio: Gmail, Slack, etc.
    PHYSICAL = "physical"  # SmartHome: lights, shades, etc.
    ROBOT = "robot"  # Future: robot manipulation
    META = "meta"  # Control flow: wait, observe, delegate


@dataclass
class Action:
    """A single action in the action space."""

    slug: str
    role: ActionRole
    domain: ActionDomain
    category: str
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# COMPOSIO DIGITAL ACTIONS — SENSORS (READ) — 241 TOTAL
# =============================================================================

COMPOSIO_SENSORS: list[str] = [
    # DISCORD (6 sensors)
    "DISCORD_GET_INVITE",
    "DISCORD_GET_MY_GUILD_MEMBER",
    "DISCORD_GET_MY_OAUTH2_AUTHORIZATION",
    "DISCORD_GET_MY_USER",
    "DISCORD_LIST_MY_GUILDS",
    "DISCORD_RETRIEVE_USER_CONNECTIONS",
    # GMAIL (23 sensors)
    "GMAIL_FETCH_EMAILS",
    "GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID",
    "GMAIL_FETCH_MESSAGE_BY_THREAD_ID",
    "GMAIL_GET_AUTO_FORWARDING_SETTINGS",
    "GMAIL_GET_CONTACTS",
    "GMAIL_GET_GMAIL_ATTACHMENT",
    "GMAIL_GET_IMAP_SETTINGS",
    "GMAIL_GET_LANGUAGE_SETTINGS",
    "GMAIL_GET_PEOPLE",
    "GMAIL_GET_POP_SETTINGS",
    "GMAIL_GET_PROFILE",
    "GMAIL_GET_SEND_AS_ALIAS",
    "GMAIL_GET_VACATION_SETTINGS",
    "GMAIL_LIST_CSE_IDENTITIES",
    "GMAIL_LIST_CSE_KEY_PAIRS",
    "GMAIL_LIST_DRAFTS",
    "GMAIL_LIST_GMAIL_HISTORY",
    "GMAIL_LIST_GMAIL_LABELS",
    "GMAIL_LIST_SEND_AS_ALIASES",
    "GMAIL_LIST_S_MIME_CONFIGS",
    "GMAIL_LIST_THREADS",
    "GMAIL_MODIFY_THREAD_LABELS",
    "GMAIL_SEARCH_PEOPLE",
    # GOOGLECALENDAR (24 sensors)
    "GOOGLECALENDAR_FIND_EVENT",
    "GOOGLECALENDAR_FIND_FREE_SLOTS",
    "GOOGLECALENDAR_GET_ACL_RULE",
    "GOOGLECALENDAR_GET_CALENDAR_FROM_CALENDAR_LIST",
    "GOOGLECALENDAR_GET_CALENDAR_SETTING",
    "GOOGLECALENDAR_GET_COLOR_DEFINITIONS",
    "GOOGLECALENDAR_GET_CURRENT_DATE_AND_TIME",
    "GOOGLECALENDAR_GET_EVENT",
    "GOOGLECALENDAR_GET_EVENT_INSTANCES",
    "GOOGLECALENDAR_GET_GOOGLE_CALENDAR",
    "GOOGLECALENDAR_LIST_ACL_RULES",
    "GOOGLECALENDAR_LIST_CALENDARS",
    "GOOGLECALENDAR_LIST_CALENDAR_LIST",
    "GOOGLECALENDAR_LIST_CALENDAR_SETTINGS",
    "GOOGLECALENDAR_LIST_EVENTS",
    "GOOGLECALENDAR_LIST_SETTINGS",
    "GOOGLECALENDAR_PATCH_CALENDAR_LIST_ENTRY",
    "GOOGLECALENDAR_QUERY_FREE_BUSY_INFORMATION",
    "GOOGLECALENDAR_SYNC_EVENTS",
    "GOOGLECALENDAR_UPDATE_CALENDAR_LIST_ENTRY",
    "GOOGLECALENDAR_WATCH_ACL_CHANGES",
    "GOOGLECALENDAR_WATCH_CALENDAR_LIST",
    "GOOGLECALENDAR_WATCH_EVENTS",
    "GOOGLECALENDAR_WATCH_SETTINGS",
    # GOOGLEDRIVE (26 sensors)
    "GOOGLEDRIVE_DOWNLOAD_A_FILE_FROM_GOOGLE_DRIVE",
    "GOOGLEDRIVE_DOWNLOAD_FILE_VIA_OPERATION",
    "GOOGLEDRIVE_EXPORT_OR_DOWNLOAD_A_FILE",
    "GOOGLEDRIVE_FIND_FILE",
    "GOOGLEDRIVE_FIND_FOLDER",
    "GOOGLEDRIVE_GET_ABOUT",
    "GOOGLEDRIVE_GET_CHANGES_START_PAGE_TOKEN",
    "GOOGLEDRIVE_GET_COMMENT",
    "GOOGLEDRIVE_GET_FILE_METADATA",
    "GOOGLEDRIVE_GET_PERMISSION",
    "GOOGLEDRIVE_GET_REPLY",
    "GOOGLEDRIVE_GET_REVISION",
    "GOOGLEDRIVE_GET_SHARED_DRIVE",
    "GOOGLEDRIVE_LIST_ACCESS_PROPOSALS",
    "GOOGLEDRIVE_LIST_APPROVALS",
    "GOOGLEDRIVE_LIST_CHANGES",
    "GOOGLEDRIVE_LIST_COMMENTS",
    "GOOGLEDRIVE_LIST_FILES_AND_FOLDERS",
    "GOOGLEDRIVE_LIST_FILE_LABELS",
    "GOOGLEDRIVE_LIST_FILE_REVISIONS",
    "GOOGLEDRIVE_LIST_PERMISSIONS",
    "GOOGLEDRIVE_LIST_REPLIES_TO_COMMENT",
    "GOOGLEDRIVE_LIST_SHARED_DRIVES",
    "GOOGLEDRIVE_STOP_WATCH_CHANNEL",
    "GOOGLEDRIVE_WATCH_DRIVE_CHANGES",
    "GOOGLEDRIVE_WATCH_FILE_FOR_CHANGES",
    # GOOGLESHEETS (13 sensors)
    "GOOGLESHEETS_BATCH_GET_SPREADSHEET",
    "GOOGLESHEETS_BATCH_GET_SPREADSHEET_VALUES_BY_DATA_FILTER",
    "GOOGLESHEETS_FIND_AND_REPLACE_IN_SPREADSHEET",
    "GOOGLESHEETS_FIND_WORKSHEET_BY_TITLE",
    "GOOGLESHEETS_GET_SHEET_NAMES",
    "GOOGLESHEETS_GET_SPREADSHEET_BY_DATA_FILTER",
    "GOOGLESHEETS_GET_SPREADSHEET_INFO",
    "GOOGLESHEETS_GET_SPREADSHEET_VALUES",
    "GOOGLESHEETS_GET_TABLE_SCHEMA",
    "GOOGLESHEETS_LIST_TABLES_IN_SPREADSHEET",
    "GOOGLESHEETS_QUERY_SPREADSHEET_TABLE",
    "GOOGLESHEETS_SEARCH_DEVELOPER_METADATA",
    "GOOGLESHEETS_SEARCH_SPREADSHEETS",
    # LINEAR (15 sensors)
    "LINEAR_DOWNLOAD_ISSUE_ATTACHMENTS",
    "LINEAR_GET_ALL_CYCLES",
    "LINEAR_GET_ALL_TEAMS",
    "LINEAR_GET_CREATE_ISSUE_DEFAULT_PARAMS",
    "LINEAR_GET_CURRENT_USER",
    "LINEAR_GET_CYCLES_BY_TEAM_ID",
    "LINEAR_GET_LABELS",
    "LINEAR_GET_LINEAR_ISSUE",
    "LINEAR_GET_TEAMS",
    "LINEAR_LIST_ISSUE_DRAFTS",
    "LINEAR_LIST_LINEAR_ISSUES",
    "LINEAR_LIST_LINEAR_PROJECTS",
    "LINEAR_LIST_LINEAR_STATES",
    "LINEAR_LIST_LINEAR_USERS",
    "LINEAR_RUN_QUERY_OR_MUTATION",
    # NOTION (20 sensors)
    "NOTION_FETCH_ALL_NOTION_BLOCK_CONTENTS",
    "NOTION_FETCH_COMMENTS",
    "NOTION_FETCH_DATABASE",
    "NOTION_FETCH_DATABASE_ROW",
    "NOTION_FETCH_NOTION_BLOCK_CHILDREN",
    "NOTION_FETCH_NOTION_BLOCK_METADATA",
    "NOTION_FETCH_NOTION_DATA",
    "NOTION_GET_ABOUT_ME",
    "NOTION_GET_ABOUT_USER",
    "NOTION_GET_PAGE_PROPERTY",
    "NOTION_LIST_DATA_SOURCE_TEMPLATES",
    "NOTION_LIST_NOTION_FILE_UPLOADS",
    "NOTION_LIST_USERS",
    "NOTION_QUERY_DATABASE",
    "NOTION_QUERY_DATABASE_WITH_FILTER",
    "NOTION_QUERY_DATA_SOURCE",
    "NOTION_RETRIEVE_COMMENT",
    "NOTION_RETRIEVE_DATABASE_PROPERTY",
    "NOTION_RETRIEVE_NOTION_FILE_UPLOAD",
    "NOTION_SEARCH_NOTION_PAGE",
    # SLACK (50 sensors)
    "SLACK_FETCH_BOT_USER_INFORMATION",
    "SLACK_FETCH_CONVERSATION_HISTORY",
    "SLACK_FETCH_ITEM_REACTIONS",
    "SLACK_FETCH_TEAM_INFO",
    "SLACK_FETCH_WORKSPACE_SETTINGS_INFORMATION",
    "SLACK_FIND_CHANNELS",
    "SLACK_FIND_USERS",
    "SLACK_GET_CHANNEL_CONVERSATION_PREFERENCES",
    "SLACK_GET_CONVERSATION_MEMBERS",
    "SLACK_GET_DO_NOT_DISTURB_STATUS_FOR_USERS",
    "SLACK_GET_REMINDER_INFORMATION",
    "SLACK_GET_REMOTE_FILE",
    "SLACK_GET_SLACK_CANVAS",
    "SLACK_GET_TEAM_DND_STATUS",
    "SLACK_LIST_ADMIN_USERS",
    "SLACK_LIST_ALL_CHANNELS",
    "SLACK_LIST_ALL_USERS",
    "SLACK_LIST_ALL_USERS_IN_A_USER_GROUP",
    "SLACK_LIST_CONVERSATIONS",
    "SLACK_LIST_PINNED_ITEMS_IN_A_CHANNEL",
    "SLACK_LIST_REMINDERS",
    "SLACK_LIST_REMOTE_FILES",
    "SLACK_LIST_SCHEDULED_MESSAGES",
    "SLACK_LIST_SCHEDULED_MESSAGES_IN_A_CHANNEL",
    "SLACK_LIST_SLACK_CANVASES",
    "SLACK_LIST_SLACK_FILES",
    "SLACK_LIST_STARRED_ITEMS",
    "SLACK_LIST_STARRED_ITEMS",
    "SLACK_LIST_TEAM_CUSTOM_EMOJIS",
    "SLACK_LIST_TEAM_REMOTE_FILES",
    "SLACK_LIST_USER_GROUPS",
    "SLACK_LIST_USER_REACTIONS",
    "SLACK_LIST_USER_REMINDERS_WITH_DETAILS",
    "SLACK_LOOKUP_CANVAS_SECTIONS",
    "SLACK_LOOKUP_USERS_BY_EMAIL",
    "SLACK_RETRIEVE_A_USER'S_IDENTITY_DETAILS",
    "SLACK_RETRIEVE_CALL_INFORMATION",
    "SLACK_RETRIEVE_CONVERSATION_INFORMATION",
    "SLACK_RETRIEVE_CONVERSATION_REPLIES",
    "SLACK_RETRIEVE_DETAILED_FILE_INFORMATION",
    "SLACK_RETRIEVE_DETAILED_USER_INFORMATION",
    "SLACK_RETRIEVE_MESSAGE_PERMALINK",
    "SLACK_RETRIEVE_REMOTE_FILE_INFO",
    "SLACK_RETRIEVE_TEAM_PROFILE_DETAILS",
    "SLACK_RETRIEVE_USER_DND_STATUS",
    "SLACK_RETRIEVE_USER_PRESENCE",
    "SLACK_RETRIEVE_USER_PROFILE_INFORMATION",
    "SLACK_SEARCH_ALL_CONTENT",
    "SLACK_SEARCH_MESSAGES",
    "SLACK_SET_CONVERSATION_READ_CURSOR",
    # TODOIST (21 sensors)
    "TODOIST_GET_ACTIVE_TASK",
    "TODOIST_GET_ALL_COLLABORATORS",
    "TODOIST_GET_ALL_COMMENTS",
    "TODOIST_GET_ALL_PERSONAL_LABELS",
    "TODOIST_GET_ALL_PROJECTS",
    "TODOIST_GET_ALL_SECTIONS",
    "TODOIST_GET_ALL_TASKS",
    "TODOIST_GET_BACKUPS",
    "TODOIST_GET_COMMENT",
    "TODOIST_GET_LABEL",
    "TODOIST_GET_PERSONAL_LABEL",
    "TODOIST_GET_PROJECT",
    "TODOIST_GET_PROJECT_COLLABORATORS",
    "TODOIST_GET_SECTION",
    "TODOIST_GET_SHARED_LABELS",
    "TODOIST_GET_SINGLE_SECTION",
    "TODOIST_GET_SPECIAL_BACKUPS",
    "TODOIST_GET_TASK",
    "TODOIST_LIST_ARCHIVED_WORKSPACE_PROJECTS",
    "TODOIST_LIST_FILTERS",
    "TODOIST_LIST_PENDING_WORKSPACE_INVITATIONS",
    # TWITTER (43 sensors)
    "TWITTER_ADD_A_LIST_MEMBER",
    "TWITTER_FETCH_LIST_MEMBERS_BY_ID",
    "TWITTER_FETCH_OPENAPI_SPECIFICATION",
    "TWITTER_FETCH_RECENT_TWEET_COUNTS",
    "TWITTER_FETCH_SPACE_TICKET_BUYERS_LIST",
    "TWITTER_FETCH_TWEET_USAGE_DATA",
    "TWITTER_GET_AUTHENTICATED_USER",
    "TWITTER_GET_A_USER'S_LIST_MEMBERSHIPS",
    "TWITTER_GET_A_USER'S_OWNED_LISTS",
    "TWITTER_GET_A_USER'S_PINNED_LISTS",
    "TWITTER_GET_BOOKMARKS_BY_USER",
    "TWITTER_GET_DM_EVENTS_BY_ID",
    "TWITTER_GET_DM_EVENTS_FOR_A_DM_CONVERSATION",
    "TWITTER_GET_FOLLOWERS_BY_USER_ID",
    "TWITTER_GET_FOLLOWING_BY_USER_ID",
    "TWITTER_GET_FULL_ARCHIVE_SEARCH_COUNTS",
    "TWITTER_GET_LIST_FOLLOWERS",
    "TWITTER_GET_MEDIA_UPLOAD_STATUS",
    "TWITTER_GET_MUTED_USERS",
    "TWITTER_GET_POST_RETWEETERS",
    "TWITTER_GET_RECENT_DIRECT_MESSAGE_EVENTS",
    "TWITTER_GET_SPACES_BY_CREATOR_IDS",
    "TWITTER_GET_SPACE_INFORMATION_BY_IDS",
    "TWITTER_GET_TWEETS_BY_IDS",
    "TWITTER_GET_TWEETS_LABEL_STREAM",
    "TWITTER_GET_USER'S_FOLLOWED_LISTS",
    "TWITTER_GET_USERS_BLOCKED_BY_USER_ID",
    "TWITTER_GET_USER_REVERSE_CHRONOLOGICAL_TIMELINE",
    "TWITTER_LIST_POSTS_TIMELINE_BY_LIST_ID",
    "TWITTER_LIST_POST_LIKERS",
    "TWITTER_LOOKUP_LIST_BY_ID",
    "TWITTER_REMOVE_A_LIST_MEMBER",
    "TWITTER_RETRIEVE_COMPLIANCE_JOBS",
    "TWITTER_RETRIEVE_COMPLIANCE_JOB_BY_ID",
    "TWITTER_RETRIEVE_DM_CONVERSATION_EVENTS",
    "TWITTER_RETRIEVE_LIKED_TWEETS_BY_USER_ID",
    "TWITTER_RETRIEVE_POSTS_FROM_A_SPACE",
    "TWITTER_RETRIEVE_POSTS_THAT_QUOTE_A_POST",
    "TWITTER_RETRIEVE_RETWEETS_OF_A_POST",
    "TWITTER_SEARCH_FOR_SPACES",
    "TWITTER_SEARCH_FULL_ARCHIVE_OF_TWEETS",
    "TWITTER_SEARCH_RECENT_TWEETS",
    "TWITTER_UPDATE_LIST_ATTRIBUTES",
]


# =============================================================================
# COMPOSIO DIGITAL ACTIONS — EFFECTORS (WRITE) — 259 TOTAL
# =============================================================================

COMPOSIO_EFFECTORS: list[str] = [
    # GMAIL (14 effectors)
    "GMAIL_BATCH_DELETE_GMAIL_MESSAGES",
    "GMAIL_BATCH_MODIFY_GMAIL_MESSAGES",
    "GMAIL_CREATE_EMAIL_DRAFT",
    "GMAIL_CREATE_LABEL",
    "GMAIL_DELETE_DRAFT",
    "GMAIL_DELETE_MESSAGE",
    "GMAIL_FORWARD_EMAIL_MESSAGE",
    "GMAIL_MODIFY_EMAIL_LABELS",
    "GMAIL_MOVE_TO_TRASH",
    "GMAIL_PATCH_LABEL",
    "GMAIL_REMOVE_LABEL",
    "GMAIL_REPLY_TO_EMAIL_THREAD",
    "GMAIL_SEND_DRAFT",
    "GMAIL_SEND_EMAIL",
    # GOOGLECALENDAR (20 effectors)
    "GOOGLECALENDAR_CLEAR_CALENDAR",
    "GOOGLECALENDAR_CREATE_ACL_RULE",
    "GOOGLECALENDAR_CREATE_A_CALENDAR",
    "GOOGLECALENDAR_CREATE_EVENT",
    "GOOGLECALENDAR_DELETE_ACL_RULE",
    "GOOGLECALENDAR_DELETE_CALENDAR",
    "GOOGLECALENDAR_DELETE_EVENT",
    "GOOGLECALENDAR_IMPORT_EVENT",
    "GOOGLECALENDAR_INSERT_CALENDAR_INTO_LIST",
    "GOOGLECALENDAR_MOVE_EVENT",
    "GOOGLECALENDAR_PATCH_ACL_RULE",
    "GOOGLECALENDAR_PATCH_CALENDAR",
    "GOOGLECALENDAR_PATCH_EVENT",
    "GOOGLECALENDAR_QUICK_ADD_EVENT",
    "GOOGLECALENDAR_REMOVE_ATTENDEE_FROM_EVENT",
    "GOOGLECALENDAR_REMOVE_CALENDAR_FROM_LIST",
    "GOOGLECALENDAR_STOP_CHANNEL",
    "GOOGLECALENDAR_UPDATE_ACL_RULE",
    "GOOGLECALENDAR_UPDATE_CALENDAR",
    "GOOGLECALENDAR_UPDATE_GOOGLE_EVENT",
    # GOOGLEDRIVE (30 effectors)
    "GOOGLEDRIVE_ADD_FILE_SHARING_PREFERENCE",
    "GOOGLEDRIVE_COPY_FILE",
    "GOOGLEDRIVE_CREATE_A_FILE_FROM_TEXT",
    "GOOGLEDRIVE_CREATE_A_FOLDER",
    "GOOGLEDRIVE_CREATE_COMMENT",
    "GOOGLEDRIVE_CREATE_FILE_OR_FOLDER",
    "GOOGLEDRIVE_CREATE_REPLY",
    "GOOGLEDRIVE_CREATE_SHARED_DRIVE",
    "GOOGLEDRIVE_CREATE_SHORTCUT_TO_FILE_FOLDER",
    "GOOGLEDRIVE_DELETE_COMMENT",
    "GOOGLEDRIVE_DELETE_FOLDER_OR_FILE",
    "GOOGLEDRIVE_DELETE_PERMISSION",
    "GOOGLEDRIVE_DELETE_REPLY",
    "GOOGLEDRIVE_DELETE_SHARED_DRIVE",
    "GOOGLEDRIVE_EDIT_FILE",
    "GOOGLEDRIVE_EMPTY_TRASH",
    "GOOGLEDRIVE_GENERATE_FILE_IDS",
    "GOOGLEDRIVE_HIDE_SHARED_DRIVE",
    "GOOGLEDRIVE_MODIFY_FILE_LABELS",
    "GOOGLEDRIVE_MOVE_FILE",
    "GOOGLEDRIVE_RESUMABLE_UPLOAD",
    "GOOGLEDRIVE_UNHIDE_SHARED_DRIVE",
    "GOOGLEDRIVE_UNTRASH_FILE",
    "GOOGLEDRIVE_UPDATE_COMMENT",
    "GOOGLEDRIVE_UPDATE_FILE_(METADATA)",
    "GOOGLEDRIVE_UPDATE_FILE_REVISION_METADATA",
    "GOOGLEDRIVE_UPDATE_PERMISSION",
    "GOOGLEDRIVE_UPDATE_REPLY",
    "GOOGLEDRIVE_UPDATE_SHARED_DRIVE",
    "GOOGLEDRIVE_UPLOAD_FILE",
    # GOOGLESHEETS (27 effectors)
    "GOOGLESHEETS_ADD_SHEET_TO_EXISTING_SPREADSHEET",
    "GOOGLESHEETS_AGGREGATE_COLUMN_DATA",
    "GOOGLESHEETS_APPEND_DIMENSION",
    "GOOGLESHEETS_APPEND_VALUES_TO_SPREADSHEET",
    "GOOGLESHEETS_BATCH_CLEAR_SPREADSHEET_VALUES",
    "GOOGLESHEETS_BATCH_CLEAR_VALUES_BY_DATA_FILTER",
    "GOOGLESHEETS_BATCH_UPDATE_SPREADSHEET",
    "GOOGLESHEETS_BATCH_UPDATE_VALUES_BY_DATA_FILTER",
    "GOOGLESHEETS_CLEAR_BASIC_FILTER",
    "GOOGLESHEETS_CLEAR_SPREADSHEET_VALUES",
    "GOOGLESHEETS_COPY_SHEET_TO_ANOTHER_SPREADSHEET",
    "GOOGLESHEETS_CREATE_A_GOOGLE_SHEET",
    "GOOGLESHEETS_CREATE_CHART_IN_GOOGLE_SHEETS",
    "GOOGLESHEETS_CREATE_SHEET_FROM_JSON",
    "GOOGLESHEETS_CREATE_SPREADSHEET_COLUMN",
    "GOOGLESHEETS_CREATE_SPREADSHEET_ROW",
    "GOOGLESHEETS_DELETE_DIMENSION_(ROWS_COLUMNS)",
    "GOOGLESHEETS_DELETE_SHEET",
    "GOOGLESHEETS_EXECUTE_SQL_ON_SPREADSHEET",
    "GOOGLESHEETS_FORMAT_CELL",
    "GOOGLESHEETS_INSERT_DIMENSION_IN_GOOGLE_SHEET",
    "GOOGLESHEETS_LOOK_UP_SPREADSHEET_ROW",
    "GOOGLESHEETS_SET_BASIC_FILTER",
    "GOOGLESHEETS_UPDATE_SHEET_PROPERTIES",
    "GOOGLESHEETS_UPDATE_SPREADSHEET_PROPERTIES",
    "GOOGLESHEETS_UPDATE_SPREADSHEET_VALUES",
    "GOOGLESHEETS_UPSERT_ROWS_(SMART_UPDATE_INSERT)",
    # LINEAR (11 effectors)
    "LINEAR_ADD_REACTION_TO_COMMENT",
    "LINEAR_CREATE_A_COMMENT",
    "LINEAR_CREATE_A_LABEL",
    "LINEAR_CREATE_LINEAR_ATTACHMENT",
    "LINEAR_CREATE_LINEAR_ISSUE",
    "LINEAR_CREATE_PROJECT",
    "LINEAR_DELETE_ISSUE",
    "LINEAR_MANAGE_DRAFT",
    "LINEAR_REMOVE_LABEL_FROM_LINEAR_ISSUE",
    "LINEAR_REMOVE_REACTION_FROM_COMMENT",
    "LINEAR_UPDATE_ISSUE",
    # NOTION (22 effectors)
    "NOTION_ADD_MULTIPLE_CONTENT_BLOCKS_(BULK,_USER_FRIENDLY)",
    "NOTION_ADD_SINGLE_CONTENT_BLOCK_TO_NOTION_PAGE_(DEPRECATED)",
    "NOTION_APPEND_CODE_BLOCKS_(CODE,_QUOTE,_EQUATION)",
    "NOTION_APPEND_LAYOUT_BLOCKS_(DIVIDER,_TOC,_COLUMNS)",
    "NOTION_APPEND_MEDIA_BLOCKS_(IMAGE,_VIDEO,_AUDIO,_FILES)",
    "NOTION_APPEND_RAW_NOTION_BLOCKS_(ADVANCED_API)",
    "NOTION_APPEND_TABLE_BLOCKS",
    "NOTION_APPEND_TASK_BLOCKS_(TO_DO,_TOGGLE,_CALLOUT)",
    "NOTION_APPEND_TEXT_BLOCKS_(PARAGRAPHS,_HEADINGS,_LISTS)",
    "NOTION_ARCHIVE_NOTION_PAGE",
    "NOTION_CREATE_COMMENT",
    "NOTION_CREATE_NOTION_DATABASE",
    "NOTION_CREATE_NOTION_FILE_UPLOAD",
    "NOTION_CREATE_NOTION_PAGE",
    "NOTION_DELETE_A_BLOCK",
    "NOTION_DUPLICATE_PAGE",
    "NOTION_INSERT_ROW_DATABASE",
    "NOTION_SEND_FILE_UPLOAD",
    "NOTION_UPDATE_BLOCK",
    "NOTION_UPDATE_DATABASE_ROW_(PAGE)",
    "NOTION_UPDATE_DATABASE_SCHEMA",
    "NOTION_UPDATE_PAGE",
    # SLACK (80 effectors)
    "SLACK_ADD_AN_EMOJI_ALIAS",
    "SLACK_ADD_A_CUSTOM_EMOJI_TO_A_SLACK_TEAM",
    "SLACK_ADD_A_REMOTE_FILE",
    "SLACK_ADD_A_STAR_TO_AN_ITEM",
    "SLACK_ADD_CALL_PARTICIPANTS",
    "SLACK_ADD_EMOJI",
    "SLACK_ADD_REACTION_TO_MESSAGE",
    "SLACK_ARCHIVE_A_PUBLIC_OR_PRIVATE_CHANNEL",
    "SLACK_ARCHIVE_A_SLACK_CONVERSATION",
    "SLACK_CLEAR_SLACK_STATUS",
    "SLACK_CLOSE_CONVERSATION_CHANNEL",
    "SLACK_CREATE_A_CHANNEL_BASED_CONVERSATION",
    "SLACK_CREATE_A_REMINDER",
    "SLACK_CREATE_A_SLACK_USER_GROUP",
    "SLACK_CREATE_CHANNEL",
    "SLACK_CREATE_SLACK_CANVAS",
    "SLACK_CUSTOMIZE_URL_UNFURL",
    "SLACK_CUSTOMIZE_URL_UNFURLING_IN_MESSAGES",
    "SLACK_DELETE_A_FILE_BY_ID",
    "SLACK_DELETE_A_MESSAGE_FROM_A_CHAT",
    "SLACK_DELETE_A_PUBLIC_OR_PRIVATE_CHANNEL",
    "SLACK_DELETE_A_SLACK_REMINDER",
    "SLACK_DELETE_FILE_COMMENT",
    "SLACK_DELETE_SCHEDULED_CHAT_MESSAGE",
    "SLACK_DELETE_SLACK_CANVAS",
    "SLACK_DELETE_USER_PROFILE_PHOTO",
    "SLACK_DISABLE_A_SLACK_USER_GROUP",
    "SLACK_EDIT_SLACK_CANVAS",
    "SLACK_ENABLE_A_USER_GROUP",
    "SLACK_END_A_CALL",
    "SLACK_END_DND_SESSION",
    "SLACK_END_SNOOZE",
    "SLACK_END_SNOOZE_MODE_IMMEDIATELY",
    "SLACK_INVITE_USERS_TO_A_SLACK_CHANNEL",
    "SLACK_INVITE_USERS_TO_CHANNEL",
    "SLACK_INVITE_USER_TO_WORKSPACE",
    "SLACK_JOIN_CONVERSATION_BY_CHANNEL_ID",
    "SLACK_LEAVE_CONVERSATION_CHANNEL",
    "SLACK_MARK_REMINDER_AS_COMPLETE",
    "SLACK_OPEN_DM",
    "SLACK_PIN_AN_ITEM_TO_A_CHANNEL",
    "SLACK_REGISTER_A_NEW_CALL_WITH_PARTICIPANTS",
    "SLACK_REGISTER_NEW_CALL_PARTICIPANTS",
    "SLACK_REMOVE_A_STAR_FROM_AN_ITEM",
    "SLACK_REMOVE_CALL_PARTICIPANTS",
    "SLACK_REMOVE_PARTICIPANTS_FROM_CALL",
    "SLACK_REMOVE_REACTION_FROM_ITEM",
    "SLACK_REMOVE_REMOTE_FILE",
    "SLACK_REMOVE_USER_FROM_CONVERSATION",
    "SLACK_RENAME_AN_EMOJI",
    "SLACK_RENAME_A_CONVERSATION",
    "SLACK_RENAME_A_SLACK_CHANNEL",
    "SLACK_REVOKE_A_FILE'S_PUBLIC_URL",
    "SLACK_SCHEDULE_MESSAGE",
    "SLACK_SEND_AN_EPHEMERAL_MESSAGE",
    "SLACK_SEND_EPHEMERAL_MESSAGE",
    "SLACK_SEND_MESSAGE",
    "SLACK_SET_A_CONVERSATION'S_PURPOSE",
    "SLACK_SET_CONVERSATION_TOPIC",
    "SLACK_SET_DND_DURATION",
    "SLACK_SET_PROFILE_PHOTO",
    "SLACK_SET_SLACK_STATUS",
    "SLACK_SET_SLACK_USER_PROFILE_INFORMATION",
    "SLACK_SET_THE_USER'S_PROFILE_IMAGE",
    "SLACK_SET_USER_PRESENCE",
    "SLACK_SHARE_A_ME_MESSAGE_IN_A_CHANNEL",
    "SLACK_SHARE_A_REMOTE_FILE_IN_CHANNELS",
    "SLACK_SHARE_FILE_PUBLIC_URL",
    "SLACK_START_CALL",
    "SLACK_START_REAL_TIME_MESSAGING_SESSION",
    "SLACK_UNARCHIVE_A_PUBLIC_OR_PRIVATE_CHANNEL",
    "SLACK_UNARCHIVE_CHANNEL",
    "SLACK_UNARCHIVE_CONVERSATION",
    "SLACK_UNPIN_MESSAGE_FROM_CHANNEL",
    "SLACK_UPDATE_AN_EXISTING_REMOTE_FILE",
    "SLACK_UPDATE_A_SLACK_MESSAGE",
    "SLACK_UPDATE_CALL_INFORMATION",
    "SLACK_UPDATE_SLACK_USER_GROUP",
    "SLACK_UPDATE_USER_GROUP_MEMBERS",
    "SLACK_UPLOAD_OR_CREATE_A_FILE_IN_SLACK",
    # TODOIST (23 effectors)
    "TODOIST_ADD_WORKSPACE",
    "TODOIST_ARCHIVE_PROJECT",
    "TODOIST_CLOSE_TASK",
    "TODOIST_CREATE_COMMENT",
    "TODOIST_CREATE_LABEL",
    "TODOIST_CREATE_PROJECT",
    "TODOIST_CREATE_SECTION",
    "TODOIST_CREATE_TASK",
    "TODOIST_DELETE_LABEL",
    "TODOIST_DELETE_PERSONAL_LABEL",
    "TODOIST_DELETE_PROJECT",
    "TODOIST_DELETE_SECTION",
    "TODOIST_DELETE_TASK",
    "TODOIST_REMOVE_SHARED_LABELS",
    "TODOIST_RENAME_SHARED_LABELS",
    "TODOIST_REOPEN_TASK",
    "TODOIST_UNARCHIVE_PROJECT",
    "TODOIST_UPDATE_COMMENT",
    "TODOIST_UPDATE_LABEL",
    "TODOIST_UPDATE_PERSONAL_LABEL",
    "TODOIST_UPDATE_PROJECT",
    "TODOIST_UPDATE_SECTION",
    "TODOIST_UPDATE_TASK",
    # TWITTER (32 effectors)
    "TWITTER_ADD_POST_TO_BOOKMARKS",
    "TWITTER_CREATE_A_LIST",
    "TWITTER_CREATE_A_POST",
    "TWITTER_CREATE_COMPLIANCE_JOB",
    "TWITTER_CREATE_GROUP_DM_CONVERSATION",
    "TWITTER_DELETE_DIRECT_MESSAGE",
    "TWITTER_DELETE_LIST",
    "TWITTER_DELETE_TWEET",
    "TWITTER_FOLLOW_A_LIST",
    "TWITTER_FOLLOW_A_USER",
    "TWITTER_LIKE_A_TWEET",
    "TWITTER_LOOK_UP_POST_BY_ID",
    "TWITTER_LOOK_UP_SPACE_BY_ID",
    "TWITTER_LOOK_UP_USERS_BY_IDS",
    "TWITTER_LOOK_UP_USERS_BY_USERNAME",
    "TWITTER_LOOK_UP_USER_BY_ID",
    "TWITTER_LOOK_UP_USER_BY_USERNAME",
    "TWITTER_MUTE_USER_BY_ID",
    "TWITTER_PIN_A_LIST",
    "TWITTER_REMOVE_A_BOOKMARKED_POST",
    "TWITTER_RETWEET_POST",
    "TWITTER_SEND_A_NEW_MESSAGE_TO_A_DM_CONVERSATION",
    "TWITTER_SEND_A_NEW_MESSAGE_TO_A_USER",
    "TWITTER_SET_REPLY_VISIBILITY",
    "TWITTER_UNFOLLOW_A_LIST",
    "TWITTER_UNFOLLOW_USER",
    "TWITTER_UNLIKE_POST",
    "TWITTER_UNMUTE_A_USER_BY_USER_ID",
    "TWITTER_UNPIN_A_LIST",
    "TWITTER_UNRETWEET_POST",
    "TWITTER_UPLOAD_LARGE_MEDIA",
    "TWITTER_UPLOAD_MEDIA",
]


# =============================================================================
# SMARTHOME PHYSICAL ACTIONS — SENSORS (GET/QUERY) — 55 TOTAL
# =============================================================================

SMARTHOME_SENSORS: list[str] = [
    # Lighting (1)
    "get_all_lights",
    # Shades (1)
    "get_all_shades",
    # Audio (1)
    "get_audio_rooms",
    # TV/Display (1)
    "get_tv_mount_state",
    # Locks (2)
    "get_lock_battery_levels",
    "get_lock_states",
    # Climate (3)
    "get_average_temp",
    "get_dsc_temperature",
    "get_hvac_temps",
    # Fireplace (1)
    "get_fireplace_state",
    # Tesla (14 sensors)
    "get_car_battery",
    "is_car_home",
    "tesla_get_vehicle_data",
    "tesla_get_charge_state",
    "tesla_get_climate_state",
    "tesla_get_drive_state",
    "tesla_get_gui_settings",
    "tesla_get_vehicle_state",
    "tesla_get_vehicle_config",
    "tesla_stream_telemetry",  # 500ms SSE streaming
    "tesla_get_alerts",
    "tesla_get_location",
    "tesla_get_odometer",
    "tesla_get_nearby_chargers",
    # Presence (4)
    "get_home_state",
    "get_presence_state",
    "is_owner_away",
    "is_owner_home",
    # Spotify (1)
    "get_spotify_state",
    # Query/Status (39)
    "find_my_get_devices",
    "get_activity_rings",
    "get_all_devices",
    "get_all_rooms",
    "get_degraded_integrations",
    "get_devices",
    "get_dsc_trouble_status",
    "get_health_state",
    "get_heart_rate",
    "get_hrv",
    "get_integration_health",
    "get_integration_status",
    "get_localization_status",
    "get_occupied_room_objects",
    "get_occupied_rooms",
    "get_open_zones",
    "get_organism_state",
    "get_owner_geofence",
    "get_owner_location",
    "get_owner_occupied_rooms",
    "get_performance_summary",
    "get_recent_motion_zones",
    "get_recommendations",
    "get_resolved_ips",
    "get_room",
    "get_room_states",
    "get_security_state",
    "get_sleep_quality",
    "get_state",
    "get_stats",
    "get_steps",
    "get_tracked_devices",
    "get_weather",
    "is_anyone_asleep",
    "is_anyone_in_bed",
    "is_any_door_open",
    "is_owner_in_room",
    "is_in_degraded_mode",
]


# =============================================================================
# SMARTHOME PHYSICAL ACTIONS — EFFECTORS (SET/CONTROL) — 77 TOTAL
# =============================================================================

SMARTHOME_EFFECTORS: list[str] = [
    # Lighting (7)
    "direct_control_light",
    "outdoor_lights_color",
    "outdoor_lights_off",
    "outdoor_lights_on",
    "outdoor_lights_pattern",
    "set_lights",
    "toggle_light",
    # Shades (3)
    "close_shades",
    "open_shades",
    "set_shades",
    # Audio (8)
    "announce",
    "announce_all",
    "find_my_play_sound",
    "find_my_play_sound_all",
    "mute_room",
    "set_audio",
    "speak_to_room",
    "tv_volume",
    # TV/Display (13)
    "direct_control_tv_power",
    "lower_tv",
    "raise_tv",
    "samsung_tv_art_mode",
    "samsung_tv_launch_app",
    "samsung_tv_off",
    "samsung_tv_on",
    "stop_tv",
    "tv_launch_app",
    "tv_notification",
    "tv_off",
    "tv_on",
    "tv_preset",
    # Locks (5)
    "lock_all",
    "outdoor_christmas",
    "outdoor_party",
    "outdoor_welcome",
    "unlock_door",
    # Climate (6)
    "direct_control_hvac",
    "set_all_temps",
    "set_away_hvac",
    "set_bed_temperature",
    "set_room_hvac_mode",
    "set_room_temp",
    # Fireplace (2)
    "fireplace_off",
    "fireplace_on",
    # Scenes (9)
    "activate_scene",
    "enter_movie_mode",
    "exit_movie_mode",
    "game_mode",
    "goodnight",
    "movie_mode",
    "set_away_mode",
    "set_room_scene",
    "welcome_home",
    # Tesla (65 effectors - ALL Fleet API commands)
    # === Charging ===
    "tesla_charge_port_door_open",
    "tesla_charge_port_door_close",
    "tesla_charge_start",
    "tesla_charge_stop",
    "tesla_charge_max_range",
    "tesla_charge_standard",
    "tesla_set_charge_limit",
    "tesla_set_charging_amps",
    "tesla_set_scheduled_charging",
    "tesla_set_scheduled_departure",
    # === Climate ===
    "tesla_auto_conditioning_start",
    "tesla_auto_conditioning_stop",
    "tesla_set_temps",
    "tesla_set_preconditioning_max",
    "tesla_remote_seat_heater_request",
    "tesla_remote_seat_cooler_request",
    "tesla_remote_steering_wheel_heater_request",
    "tesla_remote_auto_seat_climate_request",
    "tesla_set_cop_temp",
    "tesla_set_cabin_overheat_protection",
    "tesla_set_climate_keeper_mode",
    "tesla_remote_boombox",
    # === Security ===
    "tesla_door_lock",
    "tesla_door_unlock",
    "tesla_actuate_trunk",
    "tesla_honk_horn",
    "tesla_flash_lights",
    "tesla_trigger_homelink",
    "tesla_remote_start_drive",
    "tesla_set_sentry_mode",
    "tesla_set_valet_mode",
    "tesla_reset_valet_pin",
    "tesla_speed_limit_activate",
    "tesla_speed_limit_deactivate",
    "tesla_speed_limit_set_limit",
    "tesla_speed_limit_clear_pin",
    # === Media ===
    "tesla_media_toggle_playback",
    "tesla_media_next_track",
    "tesla_media_prev_track",
    "tesla_media_next_favorite",
    "tesla_media_prev_favorite",
    "tesla_media_volume_up",
    "tesla_media_volume_down",
    "tesla_adjust_volume",
    # === Windows & Sunroof ===
    "tesla_window_control",
    "tesla_sun_roof_control",
    # === Software & Updates ===
    "tesla_schedule_software_update",
    "tesla_cancel_software_update",
    # === Sharing & Navigation ===
    "tesla_share",
    "tesla_navigation_request",
    "tesla_navigation_sc_request",
    "tesla_navigation_gps_request",
    # === Energy/Powerwall ===
    "tesla_set_grid_import_export",
    "tesla_set_off_grid_vehicle_charging_reserve",
    # === Vehicle Commands ===
    "tesla_wake_up",
    "tesla_remote_auto_steering_wheel_heat_climate_request",
    "tesla_guest_mode",
    "tesla_erase_user_data",
    # === Legacy aliases for backwards compat ===
    "precondition_car",  # -> tesla_auto_conditioning_start
    "start_car_charging",  # -> tesla_charge_start
    "stop_car_charging",  # -> tesla_charge_stop
    # Spotify (7)
    "spotify_next",
    "spotify_pause",
    "spotify_play_playlist",
    "spotify_play_track",
    "spotify_previous",
    "spotify_set_volume",
    "spotify_stop",
    # Security (2)
    "arm_security",
    "disarm_security",
    # Room Control (2)
    "enter_room",
    "leave_room",
    # System (8)
    "enable_direct_control",
    "enable_optimization",
    "force_optimization_cycle",
    "force_reconnect_integration",
    "initialize",
    "shutdown_enhanced",
    "start",
    "stop",
    # Find My (3)
    "find_my_locate",
    "find_my_needs_2fa",
    "find_my_submit_2fa",
]


# =============================================================================
# META ACTIONS (Control Flow) — 7 TOTAL
# =============================================================================

META_ACTIONS: list[str] = [
    "OBSERVE",  # No-op, gather information
    "WAIT",  # Pause execution
    "DELEGATE",  # Pass to another colony
    "THINK",  # Internal reasoning
    "PLAN",  # Generate plan
    "SPEAK",  # TTS output
    "LISTEN",  # STT input
]


# =============================================================================
# BUILTIN TOOLS — SENSORS (READ/OBSERVE) — 22 TOTAL
# =============================================================================

BUILTIN_SENSORS: list[str] = [
    # File Operations — READ (3)
    "read_file",
    "search_files",
    "list_directory",
    # Code Analysis — READ (4)
    "analyze_code",
    "extract_functions",
    "measure_complexity",
    "analyze_coverage",
    # Research — READ (4)
    "search_knowledge",
    "summarize_research",
    "extract_insights",
    "synthesize_findings",
    # Debug — READ (4)
    "analyze_error",
    "debug_trace",
    "profile_execution",
    "diagnose_issue",
    # Test — READ (1)
    "measure_quality",
    # Web — READ (3)
    "web_search",
    "web_fetch",
    "browser_screenshot",
    # Shell — READ (1)
    "grep_search",
    # Memory — READ (2)
    "memory_retrieve",
    "memory_search",
]


# =============================================================================
# BUILTIN TOOLS — EFFECTORS (WRITE/MODIFY) — 21 TOTAL
# =============================================================================

BUILTIN_EFFECTORS: list[str] = [
    # File Operations — WRITE (1)
    "write_file",
    # Code Generation — WRITE (2)
    "refactor_code",
    "generate_code",
    # Debug — WRITE (1)
    "suggest_fix",
    # Test — WRITE (2)
    "generate_tests",
    "run_test_suite",
    # Build — WRITE (5)
    "build_component",
    "compile_project",
    "package_artifact",
    "deploy_service",
    "validate_build",
    # Ideation — WRITE (4)
    "brainstorm",
    "generate_ideas",
    "ideate_variations",
    "explore_concepts",
    # Web — WRITE (1)
    "browser_navigate",
    # Shell — WRITE (2)
    "shell_execute",
    "python_execute",
    # Memory — WRITE (1)
    "memory_store",
    # Colony Routing — WRITE (2)
    "route_to_colony",
    "escalate_task",
]


# Combined for backward compatibility
BUILTIN_TOOLS: list[str] = BUILTIN_SENSORS + BUILTIN_EFFECTORS


# =============================================================================
# DESKTOP/VM CONTROL — SENSORS (READ/OBSERVE) — 8 TOTAL
# =============================================================================
# Computer Use Agent (CUA) actions via Peekaboo, Lume, Parallels

DESKTOP_SENSORS: list[str] = [
    # Visual (4)
    "desktop_screenshot",  # Capture current screen
    "desktop_screenshot_window",  # Capture specific window
    "desktop_accessibility_tree",  # Get UI element tree
    "desktop_find_element",  # Find element by label/role
    # State (2)
    "desktop_list_apps",  # List running applications
    "desktop_get_frontmost",  # Get focused app
    # Clipboard (1)
    "desktop_get_clipboard",  # Read clipboard content
    # VM State (1)
    "vm_get_status",  # Get VM running/stopped status
    # CLI Sensors (5) - Cross-platform command-line queries
    "cli_which",  # Find program location (which/where)
    "cli_get_env",  # Get environment variable
    "cli_get_cwd",  # Get current working directory
    "cli_read_file",  # Read file via shell (cat/type)
    "cli_list_files",  # List directory contents (ls/dir)
]


# =============================================================================
# DESKTOP/VM CONTROL — EFFECTORS (WRITE/MODIFY) — 20 TOTAL
# =============================================================================

DESKTOP_EFFECTORS: list[str] = [
    # Mouse (6)
    "desktop_click",  # Click at coordinates or element
    "desktop_double_click",  # Double-click
    "desktop_right_click",  # Right-click (context menu)
    "desktop_drag",  # Drag from/to coordinates
    "desktop_scroll",  # Scroll direction
    "desktop_move",  # Move cursor
    # Keyboard (4)
    "desktop_type",  # Type text string
    "desktop_hotkey",  # Execute keyboard shortcut
    "desktop_press",  # Press single key
    "desktop_paste",  # Paste from clipboard
    # App Control (3)
    "desktop_launch_app",  # Launch application
    "desktop_quit_app",  # Quit application
    "desktop_focus_app",  # Bring app to foreground
    # Clipboard (1)
    "desktop_set_clipboard",  # Set clipboard content
    # VM Lifecycle (6)
    "vm_start",  # Start VM
    "vm_stop",  # Stop VM
    "vm_suspend",  # Suspend VM
    "vm_create_snapshot",  # Create snapshot
    "vm_restore_snapshot",  # Restore snapshot
    "vm_execute_command",  # Execute command in VM
    # CLI Effectors (8) - Cross-platform command-line execution
    "cli_execute",  # Execute single command (local or remote)
    "cli_execute_script",  # Execute multi-line script
    "cli_set_env",  # Set environment variable
    "cli_set_cwd",  # Change working directory
    "cli_write_file",  # Write file via shell
    "cli_install_package",  # Install pip package
    "cli_run_python",  # Execute Python code
    "cli_run_remote",  # Execute on remote target (parallels/lume/ssh)
]

# Combined desktop tools
DESKTOP_TOOLS: list[str] = DESKTOP_SENSORS + DESKTOP_EFFECTORS


# =============================================================================
# GENERATION TOOLS — OPTIMIZED DESIGN
# =============================================================================
#
# Research-based latency tiers (Dec 2025):
#   FAST (<10s):    DALL-E 3, SD XL, ElevenLabs TTS
#   MEDIUM (10-60s): Meshy 3D, Image variations
#   SLOW (1-5min):   Music gen, Video gen, Complex 3D
#   VERY SLOW (5m+): Complex video/3D, high-res outputs
#
# Redundancy eliminated:
#   - Unified status polling: gen_get_status(job_id)
#   - Unified result retrieval: gen_get_result(job_id)
#   - Unified capability query: gen_list_capabilities(modality)
#   - Unified music_generate for all music generation
#   - Moved post-processing to separate category
#
# =============================================================================

# =============================================================================
# GENERATION TOOLS — SENSORS (READ/QUERY) — 5 UNIFIED
# =============================================================================

GENERATION_SENSORS: list[str] = [
    # Unified polling (works for all modalities)
    "gen_get_status",  # Check generation status by job_id
    "gen_get_result",  # Get generated artifact by job_id
    "gen_list_capabilities",  # List models/voices/formats for modality
    # Account management
    "gen_get_credits",  # Get remaining credits (unified across services)
    "gen_get_history",  # Get generation history
]

# =============================================================================
# GENERATION TOOLS — EFFECTORS (WRITE/GENERATE) — 12 TOTAL
# =============================================================================
# Organized by modality with clear latency expectations

GENERATION_EFFECTORS: list[str] = [
    # === MUSIC — SLOW (2-3 min) ===
    "music_generate",  # Generate from prompt OR custom lyrics+style
    "music_extend",  # Extend existing song
    # === IMAGE (DALL-E, SD, FLUX) — FAST (<15s) ===
    "image_generate",  # Generate image from prompt
    "image_edit",  # Edit/inpaint existing image
    "image_variation",  # Create variations of image
    # === VIDEO (Runway, Sora) — SLOW (1-5 min) ===
    "video_generate",  # Generate video from prompt/image
    "video_extend",  # Extend existing video
    # === 3D (Meshy, Shap-E) — MEDIUM (30-60s) ===
    "model_3d_generate",  # Generate 3D model from prompt/image
    "model_3d_texture",  # Generate/apply textures
    # === AUDIO (ElevenLabs) — FAST (<5s) ===
    "audio_tts",  # Text-to-speech
    "audio_sfx",  # Generate sound effects
    "audio_clone",  # Clone voice from sample
    # === WORLD (Emu 3.5) — MEDIUM (30s-2min) ===
    "world_generate",  # Generate world from text/image prompt
    "world_explore",  # Explore/navigate generated world
    "world_expand",  # Expand world boundaries
]


# =============================================================================
# POST-PROCESSING TOOLS — EFFECTORS (TRANSFORM) — 4 TOTAL
# =============================================================================
# Non-generative operations that transform existing artifacts

POSTPROCESS_EFFECTORS: list[str] = [
    "video_compose",  # Compose/splice video segments
    "video_render",  # Render Genesis physics scene
    "model_3d_export",  # Export 3D to format (GLB, OBJ, etc.)
    "audio_mix",  # Mix/layer audio tracks
]


# Colony-specific tool recommendations
COLONY_TOOLS: dict[str, list[str]] = {
    "spark": [
        "brainstorm",
        "generate_ideas",
        "ideate_variations",
        "explore_concepts",
        "web_search",
        "search_knowledge",
        # AI generation (creative expression)
        "music_generate",
        "music_extend",
        "image_generate",  # DALL-E/SD
    ],
    "forge": [
        # Core build tools
        "build_component",
        "compile_project",
        "package_artifact",
        "deploy_service",
        "validate_build",
        # Code generation
        "generate_code",
        "refactor_code",
        # File operations
        "write_file",
        "python_execute",
        "shell_execute",
        # AI Generation (unified naming)
        "music_generate",  # SLOW (2-3min)
        "music_extend",
        "image_generate",  # DALL-E/SD - FAST (<10s)
        "image_edit",
        "image_variation",
        "video_generate",  # Runway - SLOW (1-5min)
        "video_extend",
        "model_3d_generate",  # Meshy - MEDIUM (30-60s)
        "model_3d_texture",
        "audio_tts",  # ElevenLabs - FAST (<5s)
        "audio_sfx",
        "audio_clone",
        # Post-processing
        "video_compose",
        "video_render",
        "model_3d_export",
    ],
    "flow": [
        "analyze_error",
        "suggest_fix",
        "debug_trace",
        "profile_execution",
        "diagnose_issue",
        "analyze_code",
        "grep_search",
        "shell_execute",
        # Desktop automation (computer use)
        "desktop_screenshot",
        "desktop_click",
        "desktop_type",
        "desktop_hotkey",
        "vm_execute_command",
        # CLI execution (cross-platform)
        "cli_execute",
        "cli_execute_script",
        "cli_run_remote",
        "cli_which",
        "cli_get_env",
    ],
    "nexus": [
        "search_files",
        "list_directory",
        "memory_store",
        "memory_retrieve",
        "memory_search",
        "route_to_colony",
        "escalate_task",
    ],
    "beacon": [
        "analyze_code",
        "measure_complexity",
        "search_knowledge",
        "summarize_research",
        "web_search",
    ],
    "grove": [
        "search_knowledge",
        "summarize_research",
        "extract_insights",
        "synthesize_findings",
        "read_file",
        "search_files",
        "web_search",
        "web_fetch",
    ],
    "crystal": [
        "generate_tests",
        "run_test_suite",
        "analyze_coverage",
        "measure_quality",
        "analyze_code",
        "validate_build",
        "shell_execute",
    ],
}


# =============================================================================
# AGGREGATED ACTION COUNTS
# =============================================================================


def get_action_counts() -> dict[str, int]:
    """Get counts of all action categories with Markov blanket discipline."""
    return {
        # By integration
        "composio_sensors": len(COMPOSIO_SENSORS),
        "composio_effectors": len(COMPOSIO_EFFECTORS),
        "smarthome_sensors": len(SMARTHOME_SENSORS),
        "smarthome_effectors": len(SMARTHOME_EFFECTORS),
        "builtin_sensors": len(BUILTIN_SENSORS),
        "builtin_effectors": len(BUILTIN_EFFECTORS),
        "desktop_sensors": len(DESKTOP_SENSORS),
        "desktop_effectors": len(DESKTOP_EFFECTORS),
        "generation_sensors": len(GENERATION_SENSORS),
        "generation_effectors": len(GENERATION_EFFECTORS),
        "postprocess_effectors": len(POSTPROCESS_EFFECTORS),
        "meta_actions": len(META_ACTIONS),
        # Markov blanket totals
        "total_sensors": (
            len(COMPOSIO_SENSORS)
            + len(SMARTHOME_SENSORS)
            + len(BUILTIN_SENSORS)
            + len(DESKTOP_SENSORS)
            + len(GENERATION_SENSORS)
        ),
        "total_effectors": (
            len(COMPOSIO_EFFECTORS)
            + len(SMARTHOME_EFFECTORS)
            + len(BUILTIN_EFFECTORS)
            + len(DESKTOP_EFFECTORS)
            + len(GENERATION_EFFECTORS)
            + len(POSTPROCESS_EFFECTORS)
            + len(META_ACTIONS)
        ),
        # Grand total
        "grand_total": (
            len(COMPOSIO_SENSORS)
            + len(COMPOSIO_EFFECTORS)
            + len(SMARTHOME_SENSORS)
            + len(SMARTHOME_EFFECTORS)
            + len(BUILTIN_SENSORS)
            + len(BUILTIN_EFFECTORS)
            + len(DESKTOP_SENSORS)
            + len(DESKTOP_EFFECTORS)
            + len(GENERATION_SENSORS)
            + len(GENERATION_EFFECTORS)
            + len(POSTPROCESS_EFFECTORS)
            + len(META_ACTIONS)
        ),
    }


# =============================================================================
# MOTOR DECODER ACTION LISTS (Top actions for efficient decoding)
# =============================================================================

# Primary effector actions for the motor decoder (most common)
MOTOR_DECODER_DIGITAL_ACTIONS: list[str] = COMPOSIO_EFFECTORS[:50]
MOTOR_DECODER_SMARTHOME_ACTIONS: list[str] = SMARTHOME_EFFECTORS[:50]
MOTOR_DECODER_META_ACTIONS: list[str] = META_ACTIONS


def get_motor_decoder_effectors() -> list[str]:
    """Get effector actions for motor decoder (subset for neural network heads).

    The motor decoder uses a subset of actions for efficient neural network
    classification. These are the MOST COMMON actions organized by head.

    Returns:
        128 actions: 50 digital + 50 smarthome + 7 meta + 21 builtin
    """
    return (
        MOTOR_DECODER_DIGITAL_ACTIONS
        + MOTOR_DECODER_SMARTHOME_ACTIONS
        + MOTOR_DECODER_META_ACTIONS
        + BUILTIN_EFFECTORS
    )


def get_all_effector_actions() -> list[str]:
    """Get ALL effector actions (a → η) for complete action space.

    Includes:
        - Composio WRITE (259): Send emails, post messages, create tasks
        - SmartHome SET (78): Turn on lights, announce, lock doors
        - Builtin WRITE (21): Execute code, generate content, build
        - Desktop WRITE (28): Click, type, hotkey, VM control
        - Generation WRITE (12): AI music, image, video, 3D, audio generation
        - Post-process WRITE (4): Transform/export artifacts
        - Meta (7): Control flow (observe, wait, delegate)

    Total: 409 effectors (optimized from 412)
    """
    return (
        COMPOSIO_EFFECTORS
        + SMARTHOME_EFFECTORS
        + BUILTIN_EFFECTORS
        + DESKTOP_EFFECTORS
        + GENERATION_EFFECTORS
        + POSTPROCESS_EFFECTORS
        + META_ACTIONS
    )


def get_all_sensor_actions() -> list[str]:
    """Get ALL sensor actions (η → s) for complete action space.

    Includes:
        - Composio READ (241): Fetch emails, list files, get calendar
        - SmartHome GET (55): Get lights, check locks, query presence
        - Builtin READ (22): Search files, analyze code, web search
        - Desktop READ (13): Screenshot, accessibility tree, app list
        - Generation READ (5): Unified status, result, capabilities queries

    Total: 336 sensors (optimized from 346)
    """
    return (
        COMPOSIO_SENSORS
        + SMARTHOME_SENSORS
        + BUILTIN_SENSORS
        + DESKTOP_SENSORS
        + GENERATION_SENSORS
    )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Builtin tools (Markov blanket categorized)
    "BUILTIN_EFFECTORS",
    "BUILTIN_SENSORS",
    "BUILTIN_TOOLS",  # Combined for backward compat
    # Colony mapping
    "COLONY_TOOLS",
    # Composio (Markov blanket categorized)
    "COMPOSIO_EFFECTORS",
    "COMPOSIO_SENSORS",
    # Desktop/VM Control (Markov blanket categorized)
    "DESKTOP_EFFECTORS",
    "DESKTOP_SENSORS",
    "DESKTOP_TOOLS",  # Combined
    # Generation Tools (AI Music, Image, Video, 3D, Audio) — OPTIMIZED
    "GENERATION_EFFECTORS",
    "GENERATION_SENSORS",
    # Meta
    "META_ACTIONS",
    # Motor decoder subsets
    "MOTOR_DECODER_DIGITAL_ACTIONS",
    "MOTOR_DECODER_META_ACTIONS",
    "MOTOR_DECODER_SMARTHOME_ACTIONS",
    # Post-processing Tools (Transform/Export)
    "POSTPROCESS_EFFECTORS",
    # SmartHome (Markov blanket categorized)
    "SMARTHOME_EFFECTORS",
    "SMARTHOME_SENSORS",
    "Action",
    "ActionDomain",
    "ActionRole",
    "ActionSpaceRegistry",
    # Utility functions
    "get_action_counts",
    # Registry for coupling
    "get_action_registry",
    "get_all_effector_actions",
    "get_all_sensor_actions",
    "get_motor_decoder_effectors",
    "get_tools_for_colony",
]


def get_tools_for_colony(colony_name: str) -> list[str]:
    """Get recommended tools for a specific colony.

    Args:
        colony_name: Name of the colony (spark, forge, flow, nexus, beacon, grove, crystal)

    Returns:
        List of tool names recommended for that colony
    """
    return COLONY_TOOLS.get(colony_name.lower(), [])


# =============================================================================
# ACTION SPACE REGISTRY — AUTOMATIC WORLD MODEL COUPLING
# =============================================================================
# Prevents drift between action space and world model by providing:
# 1. Runtime action registration
# 2. Automatic embedding space extension
# 3. Version tracking for consistency
# =============================================================================


class ActionSpaceRegistry:
    """Registry for automatic action space ↔ world model coupling.

    This class ensures the world model's action embedding space stays
    synchronized with the action space definitions. Any actions registered
    at runtime are automatically reflected in connected world models.

    Architecture:
        ActionSpaceRegistry ──→ World Model Action Embeddings
                             ──→ Motor Decoder Action Heads
                             ──→ RSSM Action Dimension

    Usage:
        >>> registry = get_action_registry()
        >>> registry.register_action("new_tool", ActionRole.EFFECTOR, ActionDomain.DIGITAL)
        >>> registry.sync_to_world_model(world_model)  # Extends action space
    """

    _version: int = 1  # Increment on any static change

    def __init__(self) -> None:
        # Core action lists (immutable references to module-level lists)
        self._static_sensors: list[list[str]] = [
            COMPOSIO_SENSORS,
            SMARTHOME_SENSORS,
            BUILTIN_SENSORS,
            DESKTOP_SENSORS,
            GENERATION_SENSORS,
        ]
        self._static_effectors: list[list[str]] = [
            COMPOSIO_EFFECTORS,
            SMARTHOME_EFFECTORS,
            BUILTIN_EFFECTORS,
            DESKTOP_EFFECTORS,
            GENERATION_EFFECTORS,
            POSTPROCESS_EFFECTORS,
            META_ACTIONS,
        ]

        # Runtime registrations
        self._dynamic_sensors: list[Action] = []
        self._dynamic_effectors: list[Action] = []

        # Connected models (weak references to avoid memory leaks)
        self._connected_models: list[Any] = []

        # Embedding cache (invalidated on registration)
        self._action_to_idx: dict[str, int] | None = None
        self._idx_to_action: dict[int, str] | None = None

    @property
    def version(self) -> int:
        """Current version (changes on any registration)."""
        return self._version + len(self._dynamic_sensors) + len(self._dynamic_effectors)

    def register_action(
        self,
        slug: str,
        role: ActionRole,
        domain: ActionDomain,
        description: str = "",
        parameters: dict[str, Any] | None = None,
    ) -> Action:
        """Register a new action at runtime.

        Args:
            slug: Action identifier (e.g., "my_custom_tool")
            role: SENSOR or EFFECTOR
            domain: DIGITAL, PHYSICAL, ROBOT, or META
            description: Human-readable description
            parameters: Expected parameters schema

        Returns:
            Registered Action object

        Note:
            This automatically invalidates caches and will sync to
            connected world models on next sync_to_world_model() call.
        """
        action = Action(
            slug=slug,
            role=role,
            domain=domain,
            category="custom",
            description=description,
            parameters=parameters or {},
        )

        if role == ActionRole.SENSOR:
            self._dynamic_sensors.append(action)
        else:
            self._dynamic_effectors.append(action)

        # Invalidate caches
        self._action_to_idx = None
        self._idx_to_action = None

        return action

    def get_all_actions(self) -> list[str]:
        """Get all action slugs (sensors + effectors)."""
        all_actions: list[str] = []

        # Static actions
        for sensor_list in self._static_sensors:
            all_actions.extend(sensor_list)
        for effector_list in self._static_effectors:
            all_actions.extend(effector_list)

        # Dynamic actions
        all_actions.extend(a.slug for a in self._dynamic_sensors)
        all_actions.extend(a.slug for a in self._dynamic_effectors)

        return all_actions

    def get_action_index(self, slug: str) -> int:
        """Get numeric index for action slug.

        Used for action embedding lookups in world model.
        """
        if self._action_to_idx is None:
            self._build_index()
        return self._action_to_idx.get(slug, -1)  # type: ignore[union-attr]

    def get_action_by_index(self, idx: int) -> str:
        """Get action slug by numeric index."""
        if self._idx_to_action is None:
            self._build_index()
        return self._idx_to_action.get(idx, "unknown")  # type: ignore[union-attr]

    def _build_index(self) -> None:
        """Build bidirectional index."""
        all_actions = self.get_all_actions()
        self._action_to_idx = {slug: i for i, slug in enumerate(all_actions)}
        self._idx_to_action = dict(enumerate(all_actions))

    @property
    def action_space_size(self) -> int:
        """Total number of actions (for embedding dimension)."""
        return len(self.get_all_actions())

    @property
    def effector_space_size(self) -> int:
        """Number of effector actions (for motor decoder)."""
        count = sum(len(lst) for lst in self._static_effectors)
        count += len(self._dynamic_effectors)
        return count

    @property
    def sensor_space_size(self) -> int:
        """Number of sensor actions."""
        count = sum(len(lst) for lst in self._static_sensors)
        count += len(self._dynamic_sensors)
        return count

    def connect_world_model(self, model: Any) -> None:
        """Connect a world model for automatic sync.

        Args:
            model: World model with action embedding space
        """
        import weakref

        self._connected_models.append(weakref.ref(model))

    def sync_to_world_model(self, model: Any | None = None) -> dict[str, Any]:
        """Synchronize action space to world model.

        This extends the world model's action embedding space if new
        actions have been registered since the model was created.

        Args:
            model: Specific model to sync (or syncs all connected)

        Returns:
            Sync report with counts and changes
        """
        import torch

        models = [model] if model else [ref() for ref in self._connected_models if ref()]
        report = {
            "synced_models": 0,
            "action_space_size": self.action_space_size,
            "effector_size": self.effector_space_size,
            "sensor_size": self.sensor_space_size,
            "version": self.version,
        }

        for m in models:
            if m is None:
                continue

            # Check if model has action embedding
            if hasattr(m, "organism_rssm"):
                rssm = m.organism_rssm
                current_action_dim = rssm.action_dim

                # If action space grew, we need to extend the action head
                if self.effector_space_size > current_action_dim:
                    # Create new action head with extended dimension
                    old_head = rssm.action_head
                    new_head = torch.nn.Sequential(
                        torch.nn.Linear(rssm.deter_dim + rssm.stoch_dim, rssm.deter_dim),
                        torch.nn.GELU(),
                        torch.nn.Linear(rssm.deter_dim, self.effector_space_size),
                    )

                    # Copy old weights for existing actions
                    with torch.no_grad():
                        new_head[0].weight.data[: old_head[0].weight.shape[0]] = old_head[
                            0
                        ].weight.data
                        new_head[0].bias.data[: old_head[0].bias.shape[0]] = old_head[0].bias.data
                        new_head[2].weight.data[:current_action_dim] = old_head[2].weight.data
                        new_head[2].bias.data[:current_action_dim] = old_head[2].bias.data

                    rssm.action_head = new_head.to(old_head[0].weight.device)
                    rssm.action_dim = self.effector_space_size

                    report["synced_models"] += 1

        return report

    def get_action_embedding_dim(self) -> int:
        """Get recommended embedding dimension for action representations.

        Uses a heuristic based on action space size.
        """
        size = self.action_space_size
        if size < 100:
            return 32
        elif size < 500:
            return 64
        elif size < 1000:
            return 128
        else:
            return 256


# =============================================================================
# SINGLETON FACTORY (via centralized registry)
# =============================================================================

from kagami.core.shared_abstractions.singleton_consolidation import (
    get_singleton_registry,
)

_singleton_registry = get_singleton_registry()
get_action_registry = _singleton_registry.register_sync(
    "action_space_registry", ActionSpaceRegistry
)


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    counts = get_action_counts()
    registry = get_action_registry()
    print("=" * 70)
    print("KAGAMI ACTION SPACE INVENTORY (OPTIMIZED)")
    print("=" * 70)
    print("\nSENSORS (η → s):")
    print(f"  Composio READ:     {counts['composio_sensors']:>4}")
    print(f"  SmartHome GET:     {counts['smarthome_sensors']:>4}")
    print(f"  Desktop READ:      {counts['desktop_sensors']:>4}")
    print(f"  Generation READ:   {counts['generation_sensors']:>4}  (unified polling)")
    print(f"  Builtin READ:      {counts['builtin_sensors']:>4}")
    print(f"  TOTAL SENSORS:     {counts['total_sensors']:>4}")
    print("\nEFFECTORS (a → η):")
    print(f"  Composio WRITE:    {counts['composio_effectors']:>4}")
    print(f"  SmartHome SET:     {counts['smarthome_effectors']:>4}")
    print(f"  Desktop WRITE:     {counts['desktop_effectors']:>4}")
    print(f"  Generation WRITE:  {counts['generation_effectors']:>4}  (deduplicated)")
    print(f"  Post-process:      {counts['postprocess_effectors']:>4}")
    print(f"  Builtin WRITE:     {counts['builtin_effectors']:>4}")
    print(f"  Meta Actions:      {counts['meta_actions']:>4}")
    print(f"  TOTAL EFFECTORS:   {counts['total_effectors']:>4}")
    print(f"\nGRAND TOTAL:         {counts['grand_total']:>4} actions")
    print("\nGENERATION TOOLS (by latency tier):")
    print("  FAST (<10s):   image_*, audio_* (DALL-E, ElevenLabs)")
    print("  MEDIUM (30s):  model_3d_* (Meshy, Shap-E)")
    print("  SLOW (2-5m):   music_*, video_* (MusicGen, Runway)")
    print(f"\nPOST-PROCESSING: {POSTPROCESS_EFFECTORS}")
    print("\nREGISTRY:")
    print(f"  Version:           {registry.version}")
    print(f"  Action Space:      {registry.action_space_size}")
    print(f"  Embedding Dim:     {registry.get_action_embedding_dim()}")
    print("=" * 70)
