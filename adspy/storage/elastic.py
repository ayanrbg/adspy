from dataclasses import asdict

from elasticsearch import AsyncElasticsearch

from adspy.config.settings import ELASTICSEARCH_URL
from adspy.models.ad import NormalizedAd

INDEX_NAME = "ads"


class ElasticStorage:
    def __init__(self):
        self._es = AsyncElasticsearch(ELASTICSEARCH_URL)

    async def index_ad(self, ad: NormalizedAd) -> None:
        doc = asdict(ad)
        doc.pop("raw", None)
        await self._es.index(index=INDEX_NAME, id=ad.id, document=doc)

    async def search(self, query: str, country: str | None = None, niche: str | None = None, limit: int = 20) -> list[dict]:
        must = [{"multi_match": {"query": query, "fields": ["body", "title", "page_name"]}}]
        if country:
            must.append({"term": {"country": country}})
        if niche:
            must.append({"term": {"niche": niche}})

        result = await self._es.search(
            index=INDEX_NAME,
            body={"query": {"bool": {"must": must}}, "size": limit},
        )
        return [hit["_source"] for hit in result["hits"]["hits"]]

    async def more_like_this(self, ad_id: str, limit: int = 12) -> list[dict]:
        result = await self._es.search(
            index=INDEX_NAME,
            body={
                "query": {
                    "more_like_this": {
                        "fields": ["body", "title"],
                        "like": [{"_index": INDEX_NAME, "_id": ad_id}],
                        "min_term_freq": 1,
                        "min_doc_freq": 1,
                    }
                },
                "size": limit,
            },
        )
        return [hit["_source"] for hit in result["hits"]["hits"]]
