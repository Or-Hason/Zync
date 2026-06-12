"""Backfill auto-scan settings into the singleton settings JSONB row

The scan configuration lives inside the existing ``settings.data`` JSONB blob
(no new columns). New rows get these keys from ``DEFAULT_SETTINGS_DATA`` on
first access; this migration backfills any pre-existing row so the stored blob
is self-consistent. The ``defaults || data`` merge lets existing keys win, so
only missing keys are added — already-customised values are never overwritten.

Adds (when missing) to ``settings.data``:
- ``auto_scan_enabled`` (bool, default false)
- ``scan_frequency_hours`` (int, default 3)
- ``notification_score_threshold`` (int, default 80)
- ``last_scan_at`` (null) — internal scheduler bookkeeping

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-10
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEFAULTS_JSON = (
    '{"auto_scan_enabled": false, "scan_frequency_hours": 3, '
    '"notification_score_threshold": 80, "last_scan_at": null}'
)


def upgrade() -> None:
    op.execute(
        f"UPDATE settings SET data = '{_DEFAULTS_JSON}'::jsonb || data WHERE id = 1"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE settings SET data = data "
        "- 'auto_scan_enabled' - 'scan_frequency_hours' "
        "- 'notification_score_threshold' - 'last_scan_at' "
        "WHERE id = 1"
    )
