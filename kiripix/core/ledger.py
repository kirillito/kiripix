"""The cost ledger (spec §10 "Spend", tickets 0379 and 0378): `.kiripix/cost.jsonl`, append-only, one line per Provider
call sent, with what it cost. The month's spend, the day's calls and `kiripix cost` are all read from it.

A line's `usd` is the Provider's reported usage priced from its table, or, when it reported none (or the call was cancelled
after it was sent), the estimate, with `estimated` true. A call the Provider refused is recorded only when it says it
billed it. Months and days are UTC.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from kiripix.core import atomic
from kiripix.core.errors import fail
from kiripix.core.project import Project

LEDGER_FILE = "cost.jsonl"
SCHEMA_VERSION = 1
CENTS = 6  # decimal places a sum is rounded to before it is compared with the cap: a call that fits exactly is sent


class LedgerLine(BaseModel):
    """One Provider call that was sent."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = SCHEMA_VERSION
    time: str = Field(description="When the call ended, UTC, ISO 8601.")
    call: str = Field(description="The call's ID (a pending call's, when it was approved).")
    asset: str
    provider: str
    model: str
    size: str = Field(description="WIDTHxHEIGHT.")
    quality: str
    count: int = Field(description="The images asked for.")
    images: int = Field(description="The images that came back.")
    usd: float
    estimated: bool = Field(description="True: `usd` is the pre-call estimate, the Provider reported no usage.")
    prices_date: str = Field(description="The day the Provider's price table was read.")
    usage: dict[str, int] = Field(default_factory=dict, description="The token counts the Provider reported, such as "
                                  "input_tokens and output_tokens; empty when it reported none.")
    outcome: Literal["done", "failed", "cancelled"] = Field(
        description="done, failed (billed all the same) or cancelled (during the Provider's call).")


def path(project: Project) -> Path:
    return project.state_dir / LEDGER_FILE


def now() -> datetime:
    return datetime.now(UTC)


def read(project: Project) -> list[LedgerLine]:
    found = path(project)
    if not found.is_file():
        return []
    lines: list[LedgerLine] = []
    for number, text in enumerate(found.read_text(encoding="utf-8").splitlines(), 1):
        if not text.strip():
            continue
        try:
            line = LedgerLine.model_validate_json(text)
        except ValidationError as error:
            raise fail("cost.ledger_invalid", f".kiripix/{LEDGER_FILE} line {number} is not valid: "
                       f"{error.errors()[0]['msg']}",
                       owner_action=f"Fix or remove line {number} of .kiripix/{LEDGER_FILE}.") from None
        if line.schema_version != SCHEMA_VERSION:
            raise fail("cost.ledger_invalid", f".kiripix/{LEDGER_FILE} line {number} has schema_version "
                       f"{line.schema_version}; this Kiripix reads {SCHEMA_VERSION}", owner_action="Update Kiripix.")
        lines.append(line)
    return lines


def append(project: Project, line: LedgerLine) -> None:
    atomic.append_jsonl(path(project), line.model_dump(mode="json"))


def month_of(time: str) -> str:
    return time[:7]


def spent_in_month(project: Project, month: str) -> float:
    return round(sum(line.usd for line in read(project) if month_of(line.time) == month), CENTS)


class MonthSpend(BaseModel):
    month: str = Field(description="YYYY-MM, UTC.")
    usd: float
    calls: int
    images: int
    providers: dict[str, float] = Field(description="Spend by Provider.")


class Spend(BaseModel):
    """What the calls sent since a time cost (`kiripix cost --since`, such as the start of an agent's session)."""

    since: str = Field(description="The time it starts, UTC, ISO 8601.")
    usd: float
    calls: int
    images: int
    tokens: dict[str, int] = Field(description="The reported token counts, summed.")


def since(lines: list[LedgerLine], start: datetime) -> Spend:
    chosen = [line for line in lines if datetime.fromisoformat(line.time) >= start]
    tokens: dict[str, int] = {}
    for line in chosen:
        for name, value in line.usage.items():
            tokens[name] = tokens.get(name, 0) + value
    return Spend(since=start.isoformat(timespec="seconds"), usd=round(sum(line.usd for line in chosen), CENTS),
                 calls=len(chosen), images=sum(line.images for line in chosen), tokens=dict(sorted(tokens.items())))


def by_month(lines: list[LedgerLine]) -> list[MonthSpend]:
    """The ledger summed by month (oldest first) and, within a month, by Provider."""
    months: dict[str, MonthSpend] = {}
    for line in lines:
        key = month_of(line.time)
        spend = months.setdefault(key, MonthSpend(month=key, usd=0.0, calls=0, images=0, providers={}))
        spend.usd = round(spend.usd + line.usd, CENTS)
        spend.calls += 1
        spend.images += line.images
        spend.providers[line.provider] = round(spend.providers.get(line.provider, 0.0) + line.usd, CENTS)
    return [months[m] for m in sorted(months)]


def calls_on_day(project: Project, day: str) -> int:
    return sum(1 for line in read(project) if line.time[:10] == day)
