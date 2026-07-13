"""Harvest — Universal Web Collection Engine

Extract structured data, monitor changes, collect contacts, crawl sites.
Built on Scrapling for Cloudflare bypass and anti-bot evasion.

Features that cost $50-200/mo elsewhere — free here.
"""

__version__ = "0.5.5"

from .core import Scraper as Scraper
from .extract import SchemaExtractor as SchemaExtractor
from .extract import LLMExtractor as LLMExtractor
from .extract import load_schema as load_schema
from .batch import BatchProcessor as BatchProcessor, BatchResult as BatchResult
from .driftz import DriftzMail as DriftzMail
from .contacts import ContactCollector as ContactCollector
from .notify import Notifier as Notifier
from .crawl import SiteCrawler as SiteCrawler
from .export import Exporter as Exporter
from .monitor import ChangeWatcher as ChangeWatcher
from .config import Config as Config
