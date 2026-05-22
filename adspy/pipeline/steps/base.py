from abc import ABC, abstractmethod

from adspy.models.ad import NormalizedAd


class Step(ABC):
    @abstractmethod
    async def process(self, ads: list[NormalizedAd]) -> list[NormalizedAd]:
        ...
