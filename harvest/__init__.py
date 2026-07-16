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
from .semantic_cache import SemanticCache
from .structural_diff import StructuralDiff
from .self_healing import SelfHealingParser
from .script_generator import ScriptGenerator
from .api_detector import APIDetector
from .p2p_network import P2PCacheNetwork
from .p2p.node import P2PConfig

__version__ = "0.8.0"

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
    "SemanticCache",
    "StructuralDiff",
    "SelfHealingParser",
    "ScriptGenerator",
    "APIDetector",
    "P2PCacheNetwork",
    "P2PConfig",
    "__version__",
]
