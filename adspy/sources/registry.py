from adspy.sources.facebook import FacebookSource
from adspy.sources.tiktok import TikTokSource
from adspy.sources.google import GoogleSource
from adspy.sources.direct_scraper import DirectScraper
from adspy.config.settings import FB_TOKENS

SOURCE_REGISTRY = {
    "fb_api":        FacebookSource(token_pool=FB_TOKENS),
    "tiktok":        TikTokSource(),
    "google":        GoogleSource(),
    "direct_scrape": DirectScraper(),
}
