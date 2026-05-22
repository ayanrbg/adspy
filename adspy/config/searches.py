SEARCHES = [
    {
        "id": "in_gambling",
        "country": "IN",
        "niche": "gambling",
        "keywords_ref": "gambling_in",
        "sources": ["fb_api", "tiktok", "direct_scrape"],
        "proxy_geo": "IN",
        "schedule": "*/6 hours",
        "priority": "high",
        "enabled": True,
    },
    # Future searches:
    # {"id": "br_nutra",  "country": "BR", "niche": "nutra",  "keywords_ref": "nutra_br",  "sources": ["fb_api"], "proxy_geo": "BR", "schedule": "*/6 hours", "priority": "medium", "enabled": False},
    # {"id": "de_dating", "country": "DE", "niche": "dating", "keywords_ref": "dating_de", "sources": ["fb_api"], "proxy_geo": "DE", "schedule": "*/6 hours", "priority": "medium", "enabled": False},
]
