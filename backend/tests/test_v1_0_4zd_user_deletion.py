"""v1.0.4zd — deleting a user, settled across every reference.

USER-1 went round twice. v1.0.4zb fixed `notes.author_id`, the one reference
anybody had looked at, and closed on that evidence; five more held the
account. Deleting an established user still failed with a raw 500:

    ERROR:  update or delete on table "users" violates foreign key
            constraint "user_preferences_user_id_fkey"

The rule, settled in the release brief, is that every reference to a user is
exactly one of three kinds:

  - THEIRS ALONE      — drafts, preferences. Deleted with them.
  - A RECORD          — history, published notes, events they created.
                        Kept, with the person shown as removed.
  - A GRANT OF ACCESS — team membership, event roles. Deleted.

The central test builds the worst case and asserts each object's fate
individually. The register test below is the one that matters for next time:
it fails when the schema gains a reference to `users.id` that nobody has
classified, which is the pattern that closed the backup work.
"""

import uuid

import pytest
from sqlalchemy import func, select, text

from app.api.users import delete_user
from app.models.allocation_category_exclusion import AllocationCategoryExclusion
from app.models.event import Event
from app.models.mark import MarkAssignment, MarkDefinition
from app.models.note import Note
from app.models.user import User, UserRole
from app.models.user_preferences import UserPreferences
from app.models.event_assignment import EventUserAssignment
from app.services.allocation_events_service import record_allocation_event

from tests.conftest import (
    make_category, make_event, make_participant, make_user,
)

pytestmark = pytest.mark.asyncio


# Every foreign key to `users.id`, with the fate the rule gives it. A new
# reference must be added here deliberately, which is the point.
#
#   "cascade"  — theirs alone, or a grant of access: the row goes.
#   "set_null" — a record of what happened: the row stays, the person does not.
REFERENCE_REGISTER = {
    ("auth_sessions", "user_id"): "cascade",  # session access grants, not documentary history
    ("user_preferences", "user_id"): "cascade",           # theirs alone
    ("event_user_assignments", "user_id"): "cascade",     # a grant of access
    ("notes", "author_id"): "set_null",                   # a record (drafts swept in code)
    ("allocation_events", "actor_user_id"): "set_null",   # a record
    ("mark_definitions", "created_by_user_id"): "set_null",   # a record
    ("mark_assignments", "assigned_by_user_id"): "set_null",  # a record
    ("events", "created_by"): "set_null",                 # a record
    ("allocation_category_exclusions", "created_by"): "set_null",  # a record
}

_RULE_TO_SQL = {"cascade": "CASCADE", "set_null": "SET NULL"}


async def _staff(db, email, name="Established User"):
    u = User(
        email=email,
        hashed_password="$2b$12$v1041zd.placeholder.hash.for.fixtures..",
        full_name=name, role=UserRole.STAFF,
    )
    db.add(u)
    await db.flush()
    return u


# ─── the register: the one that catches the next column ───────────────

async def test_every_reference_to_a_user_is_classified(db):
    """The schema's foreign keys to `users.id` and the register above must
    agree, both ways.

    This is what USER-1 needed and did not have. A column added without
    thought fails here rather than in somebody's browser, and a reference
    removed without updating the register fails too."""
    rows = await db.execute(text("""
        SELECT tc.table_name, kcu.column_name, rc.delete_rule
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu
          ON tc.constraint_name = ccu.constraint_name
        JOIN information_schema.referential_constraints rc
          ON tc.constraint_name = rc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY' AND ccu.table_name = 'users'
    """))
    actual = {(t, c): rule for t, c, rule in rows.all()}

    unclassified = set(actual) - set(REFERENCE_REGISTER)
    assert not unclassified, (
        f"the schema references users.id from {sorted(unclassified)}, which "
        f"nobody has decided the fate of. Classify it in REFERENCE_REGISTER "
        f"under the rule: theirs alone, a record, or a grant of access.")

    gone = set(REFERENCE_REGISTER) - set(actual)
    assert not gone, f"the register lists references that no longer exist: {sorted(gone)}"

    for key, decided in REFERENCE_REGISTER.items():
        assert actual[key] == _RULE_TO_SQL[decided], (
            f"{key[0]}.{key[1]} is {actual[key]} in the database but the "
            f"register decided {decided}")


async def test_no_bare_user_id_column_was_left_behind(db):
    """The two columns that used to hold a user id with no foreign key —
    `events.created_by` and `allocation_category_exclusions.created_by` —
    both have one now. They never blocked a delete; they just went on
    naming somebody who was gone."""
    rows = await db.execute(text("""
        SELECT tc.table_name, kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu
          ON tc.constraint_name = ccu.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY' AND ccu.table_name = 'users'
    """))
    keyed = {(t, c) for t, c in rows.all()}
    assert ("events", "created_by") in keyed
    assert ("allocation_category_exclusions", "created_by") in keyed


# ─── the worst case ───────────────────────────────────────────────────

async def test_deleting_a_user_who_has_done_everything_succeeds(db):
    """The central test. One user holding every kind of reference at once:
    a published note, an unpublished note, an event they created, history
    they wrote, a role on an event team, their preferences, a mark they
    defined and a mark they assigned. Deleting them must succeed, and each
    object's fate is asserted individually against the rule."""
    admin = await make_user(db, email="zd-deleter@test.local")
    victim = await _staff(db, "zd-established@test.local")

    ev = Event(name="Their Event", created_by=victim.id)
    db.add(ev)
    await db.flush()

    published = Note(notable_type="event", notable_id=ev.id,
                     content="the team should know", is_published=True,
                     author_id=victim.id)
    draft = Note(notable_type="event", notable_id=ev.id,
                 content="my rough thoughts", is_published=False,
                 author_id=victim.id)
    prefs = UserPreferences(user_id=victim.id, language="de")
    role = EventUserAssignment(event_id=ev.id, user_id=victim.id,
                               role="staff", permissions={"people": "read"})
    mark = MarkDefinition(event_id=ev.id, name="First aider",
                          created_by_user_id=victim.id)
    db.add_all([published, draft, prefs, role, mark])
    await db.flush()

    p = await make_participant(db, ev.id, first_name="Alice")
    assignment = MarkAssignment(event_id=ev.id, participant_id=p.id,
                                mark_id=mark.id,
                                assigned_by_user_id=victim.id)
    cat = await make_category(db, ev.id, name="Rooms")
    excl = AllocationCategoryExclusion(allocation_category_id=cat.id,
                                       participant_id=p.id,
                                       created_by=victim.id)
    db.add_all([assignment, excl])
    await db.flush()
    await record_allocation_event(
        db, event_id=ev.id, event_type="exclude", source="manual",
        participant_id=p.id, actor_user_id=victim.id,
        unit_id=None, category_id=cat.id,
        unit_name_snapshot="", category_name_snapshot="Rooms",
    )
    await db.flush()

    published_id, draft_id, ev_id = published.id, draft.id, ev.id
    mark_id, assignment_id, excl_id = mark.id, assignment.id, excl.id

    # The whole point: this used to raise.
    await delete_user(user_id=victim.id, db=db, current_user=admin)
    db.expunge_all()

    async def one(model, ident):
        return (await db.execute(
            select(model).where(model.id == ident))).scalar_one_or_none()

    async def count(model, column):
        return (await db.execute(
            select(func.count()).select_from(model)
            .where(column == victim.id))).scalar()

    # The account itself.
    assert await one(User, victim.id) is None, "the user survived"

    # THEIRS ALONE — gone.
    assert await count(UserPreferences, UserPreferences.user_id) == 0, (
        "preferences outlived their user: this is the reference that raised")
    assert await one(Note, draft_id) is None, "an unpublished note survived"

    # A GRANT OF ACCESS — gone.
    assert await count(EventUserAssignment, EventUserAssignment.user_id) == 0, (
        "an event role outlived the account that held it")

    # A RECORD — kept, naming nobody.
    kept = await one(Note, published_id)
    assert kept is not None and kept.author_id is None
    kept_ev = await one(Event, ev_id)
    assert kept_ev is not None, "the event they created was deleted with them"
    assert kept_ev.created_by is None, "the event still names its creator"
    kept_mark = await one(MarkDefinition, mark_id)
    assert kept_mark is not None and kept_mark.created_by_user_id is None
    kept_ma = await one(MarkAssignment, assignment_id)
    assert kept_ma is not None and kept_ma.assigned_by_user_id is None
    kept_ex = await one(AllocationCategoryExclusion, excl_id)
    assert kept_ex is not None and kept_ex.created_by is None
    history = (await db.execute(text(
        "SELECT count(*) FROM allocation_events WHERE actor_user_id IS NOT NULL"
    ))).scalar()
    assert history == 0, "history still names its actor"


# ─── one per reference class ──────────────────────────────────────────

async def test_preferences_go_with_their_user(db):
    """Theirs alone. The reference that produced the 500: a preferences row
    is written the moment somebody sets a language, so every real user has
    one."""
    admin = await make_user(db, email="zd-prefs-admin@test.local")
    victim = await _staff(db, "zd-prefs@test.local")
    db.add(UserPreferences(user_id=victim.id, language="ko"))
    await db.flush()

    await delete_user(user_id=victim.id, db=db, current_user=admin)
    db.expunge_all()

    left = (await db.execute(
        select(func.count()).select_from(UserPreferences)
        .where(UserPreferences.user_id == victim.id))).scalar()
    assert left == 0


async def test_an_event_role_goes_with_its_user(db):
    """A grant of access. A permission held by an account that does not
    exist is meaningless, and it is what put a ghost on the team screen."""
    admin = await make_user(db, email="zd-role-admin@test.local")
    victim = await _staff(db, "zd-role@test.local")
    ev = await make_event(db, name="Role Event")
    db.add(EventUserAssignment(event_id=ev.id, user_id=victim.id,
                               role="staff", permissions={}))
    await db.flush()

    await delete_user(user_id=victim.id, db=db, current_user=admin)
    db.expunge_all()

    left = (await db.execute(
        select(func.count()).select_from(EventUserAssignment)
        .where(EventUserAssignment.user_id == victim.id))).scalar()
    assert left == 0, "the team screen would still show them"


async def test_an_event_they_created_is_kept_and_names_nobody(db):
    """A record. Deleting a colleague must not delete their events — and
    must not leave those events naming somebody who is gone."""
    admin = await make_user(db, email="zd-event-admin@test.local")
    victim = await _staff(db, "zd-event@test.local")
    ev = Event(name="Survives Its Creator", created_by=victim.id)
    db.add(ev)
    await db.flush()
    ev_id = ev.id

    await delete_user(user_id=victim.id, db=db, current_user=admin)
    db.expunge_all()

    kept = (await db.execute(
        select(Event).where(Event.id == ev_id))).scalar_one_or_none()
    assert kept is not None, "the event was deleted with its creator"
    assert kept.created_by is None
