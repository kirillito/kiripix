"""What a Provider is (spec §8, §10 "Spend"): an image API behind one interface, with its price table.

A Provider paints: it takes a prompt, optional input images and a count, and gives back PNG images and what the call cost.
It knows nothing of Assets, budgets or ledgers; core decides whether to call it and records what it cost (tickets 0379,
0378, 0381). A Provider never reads a key from the environment: core reads the Project's `.env` and passes the key in.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field

CheckCancel = Callable[[], None]


class ProviderError(Exception):
    """A call that didn't give images: a refused request, a network error, an engine error. `billed_usd` is what the
    Provider still charges for it, when it says so (core records it in the ledger); None when nothing is known to be
    billed."""

    def __init__(self, message: str, *, billed_usd: float | None = None) -> None:
        super().__init__(message)
        self.billed_usd = billed_usd


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
    as flat token counts (`usage`), which core keeps in the ledger."""

    images: list[bytes]
    usd: float | None
    usage: dict[str, int] = field(default_factory=dict)


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
    prices_date: str = ""  # the day its price table was read
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
    def call(self, request: ProviderRequest, key: str | None, check_cancel: CheckCancel) -> ProviderResult:
        """Send the call. Raises `ProviderError` when it gives no images, and what `check_cancel` raises, as soon as it
        can (a call already sent may still be billed: core records the estimate then)."""


_PROVIDERS: dict[str, Provider] = {}


def register_provider(provider: Provider) -> None:
    """Add a Provider. The built-in ones register here; the test harness adds a fake one (`KIRIPIX_TEST_RECIPES`)."""
    _PROVIDERS[provider.id] = provider


def providers() -> dict[str, Provider]:
    return dict(_PROVIDERS)
