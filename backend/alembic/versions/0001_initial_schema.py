"""Initial schema — all 8 tables with enums, FKs, and RLS policies.

Revision ID: 0001
Revises:
Create Date: 2026-05-01
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Enums ---
    op.execute("CREATE TYPE chamber AS ENUM ('house', 'senate')")
    op.execute("CREATE TYPE vote_outcome AS ENUM ('yes', 'no', 'absent', 'present')")
    op.execute("CREATE TYPE pledge_direction AS ENUM ('yes', 'no')")
    op.execute(
        "CREATE TYPE pledge_status AS ENUM "
        "('held', 'disbursed_carrot', 'disbursed_stick', 'refunded')"
    )
    op.execute("CREATE TYPE disbursement_status AS ENUM ('pending', 'executed')")

    # --- representatives ---
    op.create_table(
        "representatives",
        sa.Column("id", sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("bioguide_id", sa.Text, nullable=False, unique=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("party", sa.Text, nullable=False),
        sa.Column("chamber", sa.Enum("house", "senate", name="chamber", create_type=False), nullable=False),
        sa.Column("state", sa.Text, nullable=False),
        sa.Column("district", sa.Integer, nullable=True),
        sa.Column("photo_url", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("next_election_date", sa.Date, nullable=True),
    )
    op.create_index("ix_representatives_bioguide_id", "representatives", ["bioguide_id"])

    # --- bills ---
    op.create_table(
        "bills",
        sa.Column("id", sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("congress_bill_id", sa.Text, nullable=False, unique=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("summary_ai", sa.Text, nullable=True),
        sa.Column("introduced_date", sa.Date, nullable=True),
        sa.Column("status", sa.Text, nullable=True),
    )

    # --- votes ---
    op.create_table(
        "votes",
        sa.Column("id", sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("bill_id", sa.Uuid, sa.ForeignKey("bills.id"), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("congress_vote_id", sa.Text, nullable=True),
    )
    op.create_index("ix_votes_bill_id", "votes", ["bill_id"])

    # --- vote_outcomes ---
    op.create_table(
        "vote_outcomes",
        sa.Column("id", sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("vote_id", sa.Uuid, sa.ForeignKey("votes.id"), nullable=False),
        sa.Column("representative_id", sa.Uuid, sa.ForeignKey("representatives.id"), nullable=False),
        sa.Column("outcome", sa.Enum("yes", "no", "absent", "present", name="vote_outcome", create_type=False), nullable=False),
    )
    op.create_index("ix_vote_outcomes_vote_id", "vote_outcomes", ["vote_id"])
    op.create_index("ix_vote_outcomes_representative_id", "vote_outcomes", ["representative_id"])

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("email", sa.Text, nullable=False, unique=True),
        sa.Column("zip_code", sa.Text, nullable=True),
        sa.Column("verification_tier", sa.Integer, nullable=False, server_default="1"),
        sa.Column("total_pledged_lifetime_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("stripe_customer_id", sa.Text, nullable=True),
    )

    # --- user_representatives ---
    op.create_table(
        "user_representatives",
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("representative_id", sa.Uuid, sa.ForeignKey("representatives.id"), primary_key=True),
        sa.Column("is_confirmed", sa.Boolean, nullable=False, server_default="false"),
    )

    # --- pledges ---
    op.create_table(
        "pledges",
        sa.Column("id", sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("vote_id", sa.Uuid, sa.ForeignKey("votes.id"), nullable=False),
        sa.Column("representative_id", sa.Uuid, sa.ForeignKey("representatives.id"), nullable=False),
        sa.Column("direction", sa.Enum("yes", "no", name="pledge_direction", create_type=False), nullable=False),
        sa.Column("amount_cents", sa.Integer, nullable=False),
        sa.Column("stripe_payment_intent_id", sa.Text, nullable=True),
        sa.Column("status", sa.Enum("held", "disbursed_carrot", "disbursed_stick", "refunded", name="pledge_status", create_type=False), nullable=False, server_default="'held'"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_pledges_user_id", "pledges", ["user_id"])
    op.create_index("ix_pledges_vote_id", "pledges", ["vote_id"])

    # --- disbursements ---
    op.create_table(
        "disbursements",
        sa.Column("id", sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("election_date", sa.Date, nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_carrot_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_stick_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.Enum("pending", "executed", name="disbursement_status", create_type=False), nullable=False, server_default="'pending'"),
    )

    # --- Row-Level Security ---
    # Enable RLS on user-scoped tables
    for table in ("users", "user_representatives", "pledges"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")

    # users: own row only
    op.execute("""
        CREATE POLICY users_self ON users
        USING (id = auth.uid())
        WITH CHECK (id = auth.uid())
    """)

    # user_representatives: own rows only
    op.execute("""
        CREATE POLICY user_representatives_self ON user_representatives
        USING (user_id = auth.uid())
        WITH CHECK (user_id = auth.uid())
    """)

    # pledges: own rows only
    op.execute("""
        CREATE POLICY pledges_self ON pledges
        USING (user_id = auth.uid())
        WITH CHECK (user_id = auth.uid())
    """)

    # Public read on reference tables (no RLS needed — default is open read)
    # representatives, bills, votes, vote_outcomes, disbursements are publicly readable


def downgrade() -> None:
    for table in ("users", "user_representatives", "pledges"):
        op.execute(f"DROP POLICY IF EXISTS {table.rstrip('s')}_self ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    for table in (
        "disbursements", "pledges", "user_representatives",
        "users", "vote_outcomes", "votes", "bills", "representatives",
    ):
        op.drop_table(table)

    for enum in ("disbursement_status", "pledge_status", "pledge_direction", "vote_outcome", "chamber"):
        op.execute(f"DROP TYPE IF EXISTS {enum}")
