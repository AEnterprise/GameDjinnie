from enum import IntEnum

from tortoise.models import Model
from tortoise import fields


class TestStatus(IntEnum):
    STARTED = 0
    END_PHASE = 1
    ENDED = 2


class GameTest(Model):
    id = fields.IntField(pk=True)
    announcement = fields.BigIntField()
    reaction = fields.CharField(max_length=16)  # just to be safe with unicode shenanigans
    ends_at = fields.DatetimeField()
    status = fields.IntEnumField(TestStatus, default=TestStatus.STARTED)


class GameCode(Model):
    code = fields.CharField(pk=True, max_length=50)
    claimed_by = fields.BigIntField(null=True)
    game_test = fields.ForeignKeyField("models.GameTest", related_name="codes")


class ParticipantStatus(IntEnum):
    PARTICIPATED = 0
    NOT_PARTICIPATED = 1


class Participants(Model):
    game_test = fields.ForeignKeyField("models.GameTest", related_name="participants")
    user = fields.BigIntField()
    status = fields.IntEnumField(ParticipantStatus, default=ParticipantStatus.PARTICIPATED)
