from enum import IntEnum

from tortoise.models import Model
from tortoise import fields

class TestStatus(IntEnum):
    STARTED = 0
    ENDING = 1
    ENDED = 2

class Game(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class GameCode(Model):
    code = fields.CharField(pk=True, max_length=50)
    claimed_by = fields.BigIntField(null=True)
    game = fields.ForeignKeyField("models.Game", related_name="codes")

    def __str__(self):
        return self.code


class GameTest(Model):
    game = fields.ForeignKeyField("models.Game", related_name="announcements")
    message = fields.BigIntField(unique=True)
    end = fields.DatetimeField()
    status = fields.IntEnumField(TestStatus, default=TestStatus.STARTED)

    def __str__(self):
        return f"Test {self.game}-{self.message}: {TestStatus._value2member_map_[self.status]} (end at {self.end})"
