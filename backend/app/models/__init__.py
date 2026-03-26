from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.models.source import Source
from app.models.product import Product
from app.models.price_observation import PriceObservation
from app.models.price_change import PriceChange
from app.models.price_alert import PriceAlert
from app.models.crawl_run import CrawlRun
from app.models.config import Config

__all__ = ["Base", "Source", "Product", "PriceObservation", "PriceChange", "PriceAlert", "CrawlRun", "Config"]
