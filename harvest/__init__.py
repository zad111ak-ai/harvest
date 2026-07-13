"""Harvest — Universal Web Collection Engine

Extract structured data, monitor changes, collect contacts, crawl sites.
Built on Scrapling for Cloudflare bypass and anti-bot evasion.

Features that cost $50-200/mo elsewhere — free here.
"""

from .core import Scraper
from .extract import SchemaExtractor, LLMExtractor
from .monitor import ChangeWatcher
from .notify import Notifier
from .pipeline import Pipeline
from .config import Config
from .contacts import ContactCollector
from .batch import BatchProcessor
from .driftz import DriftzMail
from .crawl import SiteCrawler
from .export import Exporter
from .dashboard import Dashboard
from .robots import RobotsChecker
from .logger import StructuredLogger
from .preprocess import clean_html_for_llm
from .failures import FailureTracker

__version__ = "0.6.1"

__all__ = [
    "Scraper",
    "SchemaExtractor",
    "LLMExtractor",
    "ChangeWatcher",
    "Notifier",
    "Pipeline",
    "Config",
    "ContactCollector",
    "BatchProcessor",
    "DriftzMail",
    "SiteCrawler",
    "Exporter",
    "Dashboard",
    "RobotsChecker",
    "StructuredLogger",
    "clean_html_for_llm",
    "FailureTracker",
    "__version__",
]
