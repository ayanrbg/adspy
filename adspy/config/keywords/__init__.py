import importlib


def load_keywords(keywords_ref: str) -> list[str]:
    """Load keywords list by reference name (e.g. 'gambling_in')."""
    module = importlib.import_module(f"adspy.config.keywords.{keywords_ref}")
    return module.KEYWORDS
