import enum

import sqlalchemy as sa


class Chamber(str, enum.Enum):
    house = "house"
    senate = "senate"


class VoteOutcome(str, enum.Enum):
    yes = "yes"
    no = "no"
    absent = "absent"
    present = "present"


class PledgeDirection(str, enum.Enum):
    yes = "yes"
    no = "no"


class PledgeStatus(str, enum.Enum):
    held = "held"
    disbursed_carrot = "disbursed_carrot"
    disbursed_stick = "disbursed_stick"
    refunded = "refunded"


class DisbursementStatus(str, enum.Enum):
    pending = "pending"
    executed = "executed"


chamber_enum = sa.Enum(Chamber, name="chamber")
vote_outcome_enum = sa.Enum(VoteOutcome, name="vote_outcome")
pledge_direction_enum = sa.Enum(PledgeDirection, name="pledge_direction")
pledge_status_enum = sa.Enum(PledgeStatus, name="pledge_status")
disbursement_status_enum = sa.Enum(DisbursementStatus, name="disbursement_status")

ENUM_NAMES: set[str] = {
    "chamber",
    "vote_outcome",
    "pledge_direction",
    "pledge_status",
    "disbursement_status",
}
