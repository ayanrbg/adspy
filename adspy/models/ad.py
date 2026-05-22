from dataclasses import dataclass, field


@dataclass
class NormalizedAd:
    id: str                       # "fb_123" / "tt_456" — source prefix
    source: str                   # "fb_api" / "tiktok" / ...
    page_id: str | None = None
    page_name: str | None = None
    body: str = ""
    title: str = ""
    snapshot_url: str | None = None

    # Filled by pipeline
    screenshot_url: str | None = None
    image_urls: list[str] = field(default_factory=list)
    video_urls: list[str] = field(default_factory=list)
    has_video: bool = False

    country: str = ""
    niche: str = ""
    niche_confidence: float = 0.0

    start_date: str | None = None
    stop_date: str | None = None
    days_active: int | None = None
    is_active: bool = True

    impressions_min: int = 0
    impressions_max: int = 0

    raw: dict = field(default_factory=dict)
