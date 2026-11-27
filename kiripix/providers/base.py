"""What a Provider is (spec §8, §10 "Spend"): an image API behind one interface, with its price table.

A Provider paints: it takes a prompt, optional input images and a count, and gives back PNG images and what the call cost.
It knows nothing of Assets, budgets or ledgers; core decides whether to call it and records what it cost (tickets 0379,
0378, 0381). A Provider never reads a key from the environment: core reads the Project's `.env` and passes the key in.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

CheckCancel = Callable[[], None]
Wait = Callable[[float], None]
"""`wait(seconds)`: how a Provider waits between polls of a job. Core binds it to `kiripix.core.cancel.sleep`, which raises
as soon as the Command is cancelled. A Provider never sleeps itself and never imports core."""


class ProviderError(Exception):
    """A call that didn't give images: a refused request, a network error, an engine error. `billed_usd` is what the
    Provider still charges for it, when it says so (core records it in the ledger); None when nothing is known to be
    billed. `billed_generations`: the same charge in the Provider's generations, when it charged in those."""

    def __init__(self, message: str, *, billed_usd: float | None = None, billed_generations: float | None = None) -> None:
        super().__init__(message)
        self.billed_usd = billed_usd
        self.billed_generations = billed_generations


@dataclass(frozen=True)
class InputImage:
    """An image sent with an edit: its PNG bytes and a name for the request."""

    name: str
    png: bytes


@dataclass(frozen=True)
class ProviderRequest:
    """One call. `size` is (width, height) in px, already one the Provider accepts (`Provider.fit_size`). With no
    `images` it is a generation; with images, an edit of the first, the rest references. An edited first image is already
    at `size` (core pads or shrinks it to the size sent, and maps each result back). `mask`: a PNG at `size` whose alpha is
    0 where the Provider paints and 255 where it keeps the first image (an `extend` canvas's kept strips). `input_fidelity`:
    how closely the Provider keeps the input (`high`, `low`), None to leave it out."""

    prompt: str
    model: str
    size: tuple[int, int]
    quality: str
    count: int
    images: tuple[InputImage, ...] = ()
    mask: bytes | None = None
    input_fidelity: str | None = None


@dataclass(frozen=True)
class ProviderResult:
    """What a call gave: the images as PNG bytes, in order; its cost from the Provider's reported usage priced from the
    price table (`usd`), or None when the Provider reported none (core records the estimate, marked so); and that usage
    as flat token counts (`usage`), which core keeps in the ledger. `generations`: what a Provider that charges in
    generations (PixelLab) charged, as charged (a float: 0.25 is common), None when it charged in USD or reported nothing."""

    images: list[bytes]
    usd: float | None
    usage: dict[str, int] = field(default_factory=dict)
    generations: float | None = None


@dataclass(frozen=True)
class OperationRequest:
    """One operation of a Provider that isn't an image edit: a `name` from `Provider.operations`, its `params` (JSON-like
    values: a character ID, a description, a canvas, keypoints, a frame count, a direction, a `state_name`) and its
    `images` by role (PNG bytes). Which params and image roles each operation reads is the Provider's to document
    (PixelLab's: `kiripix/providers/pixellab.py`). One request type for all of them keeps core's plan (a list of
    operations, each with an estimate) and a pending call's JSON free of a class per operation."""

    name: str
    params: dict[str, Any] = field(default_factory=dict)
    images: dict[str, bytes] = field(default_factory=dict)


@dataclass(frozen=True)
class OperationResult:
    """What an operation gave, beside the charge (`usd`, `generations`: as `ProviderResult`'s). `character_id`: the
    character it made, when it makes one. `archive`: that character's ZIP, as bytes (unpacked and filtered by core).
    `images`: PNG bytes in order (frames). `data`: structured answers (a rig, keypoints, and notes such as
    `first_frame_is_ours`). `job_ids`: the Provider's own IDs for what it ran, for the record."""

    name: str
    usd: float | None
    generations: float | None = None
    character_id: str | None = None
    archive: bytes | None = None
    images: list[bytes] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    job_ids: list[str] = field(default_factory=list)


class Provider(ABC):
    """An image API. Its price table lives with it, dated, so an estimate never depends on a call's response."""

    id: str
    description: str
    key_name: str | None = None  # the `.env` entry its key is read from; None for a Provider that needs no key
    default_model: str = ""
    default_quality: str = ""
    qualities: tuple[str, ...] = ()
    max_count: int = 1  # images one call may ask for
    max_images_in: int = 0  # input images an edit may send; 0: no edits
    edits = True  # it edits the first input image (`--look`, `--state`, `--emotion`, `--side`); False: it takes only references
    prices_date: str = ""  # the day its price table was read
    terms: str = ""  # one line: what the Provider's terms say about the output, shown with the Provider; empty: none noted
    operations: tuple[str, ...] = ()  # names `operate` takes; empty: the plain `call` only (OpenAI)
    endpoints: dict[str, str] = {}  # an operation's name -> the Provider's own endpoint, for the ledger and the plan; else its name
    rerenders_kept_strip = False  # an edit repaints the whole canvas, kept strip too (GPT Image, ticket 0377)

    def fidelities(self, model: str) -> tuple[str, ...]:
        """The `input_fidelity` values the model takes; none: it takes no such setting, and it is left out."""
        return ()

    @abstractmethod
    def estimate_usd(self, model: str, size: tuple[int, int], quality: str, count: int, images_in: int,
                     prompt_chars: int) -> float:
        """The price of a call, from the price table, before it is sent."""

    @abstractmethod
    def fit_size(self, model: str, wanted: tuple[int, int]) -> tuple[int, int]:
        """The size nearest `wanted` (width, height) that the model takes, at the same aspect where it can."""

    @abstractmethod
    def call(self, request: ProviderRequest, key: str | None, check_cancel: CheckCancel,
             wait: Wait | None = None) -> ProviderResult:
        """Send the call. Raises `ProviderError` when it gives no images, and what `check_cancel` raises, as soon as it
        can (a call already sent may still be billed: core records the estimate then). `wait`: how a Provider whose
        calls are jobs waits between polls (see `Wait`); one that answers at once ignores it."""

    def estimate_operation(self, request: OperationRequest) -> float:
        """The price in USD of one operation, from the price table, before it is sent."""
        raise ProviderError(f"the {self.id} Provider has no operation '{request.name}'")

    def operate(self, request: OperationRequest, key: str | None, check_cancel: CheckCancel,
                wait: Wait) -> OperationResult:
        """Send one operation (see `OperationRequest`). Raises `ProviderError` (with `billed_usd` when it charged) and
        what `check_cancel` or `wait` raises: a job in flight is cancelled at the Provider first."""
        raise ProviderError(f"the {self.id} Provider has no operation '{request.name}'")


_PROVIDERS: dict[str, Provider] = {}


def register_provider(provider: Provider) -> None:
    """Add a Provider. The built-in ones register here; the test harness adds a fake one (`KIRIPIX_TEST_RECIPES`)."""
    _PROVIDERS[provider.id] = provider


def providers() -> dict[str, Provider]:
    return dict(_PROVIDERS)
