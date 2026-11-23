"""Image API Providers (spec §8, §10 "Spend"): a prompt and input images in, PNG images and their cost out. Uses only
`checks` and `ops`. Core reads the key, checks the budget and keeps the ledger (tickets 0379, 0378, 0381)."""

from kiripix.providers.base import (
    CheckCancel, InputImage, Provider, ProviderError, ProviderRequest, ProviderResult, providers, register_provider,
)
from kiripix.providers.openai import OpenAI

register_provider(OpenAI())

__all__ = [
    "CheckCancel",
    "InputImage",
    "Provider",
    "ProviderError",
    "ProviderRequest",
    "ProviderResult",
    "providers",
    "register_provider",
]
