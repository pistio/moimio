"""ORM models — import all here so Alembic can discover them."""

from app.models.user import User, UserRole  # noqa: F401
from app.models.event import Event, EventStatus  # noqa: F401
from app.models.participant import Participant, RegistrationStatus  # noqa: F401
from app.models.event_field_config import EventFieldConfig  # noqa: F401
from app.models.custom_field import CustomFieldDefinition, CustomFieldValue  # noqa: F401
from app.models.note import Note  # noqa: F401
from app.models.allocation_category import AllocationCategory  # noqa: F401
from app.models.allocation_unit import AllocationUnit  # noqa: F401
from app.models.allocation import Allocation  # noqa: F401
from app.models.allocation_category_exclusion import AllocationCategoryExclusion  # noqa: F401
from app.models.allocation_event import (  # noqa: F401
    AllocationEvent,
    AllocationEventType,
    AllocationEventSource,
)
from app.models.user_preferences import UserPreferences  # noqa: F401
from app.models.checkin_field import CheckInField  # noqa: F401
from app.models.checkin_value import CheckInValue  # noqa: F401
from app.models.mark import MarkDefinition, MarkAssignment  # noqa: F401
from app.models.event_assignment import EventUserAssignment  # noqa: F401
from app.models.preference_request import ParticipantPreferenceRequest  # noqa: F401
# LEGAL-1: the one-row table of installation-wide settings
from app.models.workspace_settings import WorkspaceSettings  # noqa: F401
# v1.0.0g: outbound webhook subsystem
from app.models.outbound_webhook import (  # noqa: F401
    OutboundWebhookEndpoint,
    OutboundWebhookDelivery,
    WebhookEndpointState,
    WebhookEndpointManagedBy,
    WebhookDeliveryStatus,
)
from app.models.hosted_access import AuthSession, BootstrapGrant  # noqa: F401
