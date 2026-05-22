from abc import ABC, abstractmethod

from adspy.models.ad import NormalizedAd


class AdSource(ABC):
    name: str

    @abstractmethod
    async def fetch(self, search_config: dict) -> list[NormalizedAd]:
        """Collect ads and return in normalized format."""
        ...
