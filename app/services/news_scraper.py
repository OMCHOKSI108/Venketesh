import asyncio
import feedparser
import re
from datetime import datetime, timezone
from typing import Optional
import httpx
from bs4 import BeautifulSoup
from app.core.logging_config import logger


class NewsScraper:
    RSS_FEEDS = [
        {
            "name": "Yahoo Finance",
            "url": "https://finance.yahoo.com/news/rssindex",
            "category": "general",
        },
        {
            "name": "Yahoo Markets",
            "url": "https://markets.businessinsider.com/rss",
            "category": "markets",
        },
        {
            "name": "CNBC Markets",
            "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=1000064",
            "category": "markets",
        },
        {
            "name": "MarketWatch",
            "url": "https://feeds.marketwatch.com/marketwatch/topstories/",
            "category": "general",
        },
        {
            "name": "Investing.com",
            "url": "https://www.investing.com/rss/news.rss",
            "category": "general",
        },
        {
            "name": "Google Markets",
            "url": "https://news.google.com/rss/search?q=stock+market&hl=en-US&gl=US&ceid=US:en",
            "category": "markets",
        },
        {
            "name": "Google Finance India",
            "url": "https://news.google.com/rss/search?q=NIFTY+SENSEX+BSE&hl=en-IN&gl=IN&ceid=IN:en",
            "category": "india",
        },
        {
            "name": "Google US Markets",
            "url": "https://news.google.com/rss/search?q=DOW+NASDAQ+S%26P&hl=en-US&gl=US&ceid=US:en",
            "category": "us",
        },
    ]

    SCRAPE_URLS = [
        {
            "name": "Economic Times",
            "url": "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/ED76E8F3B36C9C6B651D1DCCDC5E8A52.cms",
            "selector": "item",
        },
        {
            "name": "MoneyControl",
            "url": "https://www.moneycontrol.com/rss/business.xml",
            "selector": "item",
        },
        {
            "name": "NDTV Business",
            "url": "https://feeds.feedburner.com/ndtvprofit-LatestNews",
            "selector": "item",
        },
    ]

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=15.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                },
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    def parse_rss_item(self, entry: dict, source: str) -> Optional[dict]:
        try:
            title = getattr(entry, "title", "") or ""
            link = getattr(entry, "link", "") or ""

            if hasattr(entry, "published"):
                published = entry.published
            elif hasattr(entry, "updated"):
                published = entry.updated
            else:
                published = datetime.now(timezone.utc).isoformat()

            summary = ""
            if hasattr(entry, "summary"):
                summary = entry.summary
            elif hasattr(entry, "description"):
                summary = entry.description

            summary = self._clean_html(summary)

            if not title:
                return None

            return {
                "title": title[:500],
                "summary": summary[:1000] if summary else "",
                "source": source,
                "url": link,
                "published_at": published,
            }
        except Exception as e:
            logger.error("rss_parse_error", error=str(e))
            return None

    def _clean_html(self, text: str) -> str:
        if not text:
            return ""
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        text = text.strip()
        return text[:2000]

    async def fetch_rss_feed(self, feed_info: dict) -> list[dict]:
        client = await self.get_client()
        articles = []

        try:
            response = await client.get(feed_info["url"], timeout=10.0)

            if response.status_code != 200:
                return []

            feed = feedparser.parse(response.text)

            for entry in feed.entries[:15]:
                article = self.parse_rss_item(entry, feed_info["name"])
                if article:
                    articles.append(article)

            logger.info("rss_fetched", source=feed_info["name"], count=len(articles))

        except Exception as e:
            logger.error("rss_fetch_error", source=feed_info["name"], error=str(e))

        return articles

    async def fetch_all_rss(self) -> list[dict]:
        all_articles = []

        tasks = [self.fetch_rss_feed(feed) for feed in self.RSS_FEEDS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                all_articles.extend(result)

        all_articles.sort(key=lambda x: x.get("published_at", ""), reverse=True)

        return all_articles[:100]

    async def scrape_webpage(self, scrape_info: dict) -> list[dict]:
        client = await self.get_client()
        articles = []

        try:
            response = await client.get(scrape_info["url"], timeout=15.0)

            if response.status_code != 200:
                return []

            soup = BeautifulSoup(response.text, "lxml")

            if scrape_info["selector"] == "item":
                items = soup.find_all("item")
            else:
                items = soup.select(scrape_info["selector"])

            for item in items[:10]:
                try:
                    title_elem = item.find("title")
                    title = title_elem.get_text(strip=True) if title_elem else ""

                    link_elem = item.find("link")
                    link = link_elem.get_text(strip=True) if link_elem else ""
                    if not link and link_elem:
                        link = str(link_elem)

                    desc_elem = item.find("description") or item.find("summary")
                    description = desc_elem.get_text(strip=True) if desc_elem else ""

                    pub_elem = item.find("pubdate") or item.find("published")
                    pub_date = pub_elem.get_text(strip=True) if pub_elem else ""

                    if title:
                        articles.append(
                            {
                                "title": title[:500],
                                "summary": self._clean_html(description)[:1000],
                                "source": scrape_info["name"],
                                "url": link,
                                "published_at": pub_date or datetime.now(timezone.utc).isoformat(),
                            }
                        )
                except Exception as e:
                    continue

            logger.info("webpage_scrape", source=scrape_info["name"], count=len(articles))

        except Exception as e:
            logger.error("scrape_error", source=scrape_info["name"], error=str(e))

        return articles

    async def fetch_all(self) -> list[dict]:
        logger.info("news_scraper_fetch_start")

        rss_task = self.fetch_all_rss()
        scrape_tasks = [self.scrape_webpage(info) for info in self.SCRAPE_URLS]

        rss_articles = await rss_task
        scrape_results = await asyncio.gather(*scrape_tasks, return_exceptions=True)

        all_articles = rss_articles[:]
        for result in scrape_results:
            if isinstance(result, list):
                all_articles.extend(result)

        all_articles.sort(key=lambda x: x.get("published_at", ""), reverse=True)

        unique_articles = self._deduplicate(all_articles)

        logger.info("news_scraper_complete", total=len(unique_articles))
        return unique_articles[:50]

    def _deduplicate(self, articles: list[dict]) -> list[dict]:
        seen_titles = set()
        unique = []

        for article in articles:
            title_lower = article["title"].lower()
            if title_lower not in seen_titles:
                seen_titles.add(title_lower)
                unique.append(article)

        return unique


news_scraper = NewsScraper()
