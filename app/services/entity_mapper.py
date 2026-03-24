import re
from typing import Optional
from app.core.constants import SUPPORTED_SYMBOLS
from app.core.logging_config import logger


class EntityMapper:
    SYMBOL_PATTERNS = {
        "NIFTY": [
            r"\bNIFTY\s*50\b", r"\bNSE\s*NIFTY\b", r"\bNifty\s*50\b",
            r"\bNIFTY\b(?!\s*(IT|Bank|Finance|Media|Auto|Pharma|FMCG|IT))
        ],
        "BANKNIFTY": [
            r"\bBank\s*Nifty\b", r"\bNIFTY\s*Bank\b", r"\bBankNifty\b",
            r"\bNifty\s*Bank\b"
        ],
        "SENSEX": [
            r"\bSENSEX\b", r"\bBSE\s*Sensex\b", r"\bBombay\s*Stock\s*Exchange\b",
            r"\bBSE\s*30\b"
        ],
        "NIFTYIT": [
            r"\bNIFTY\s*IT\b", r"\bNifty\s*IT\b", r"\bIT\s*Index\b",
            r"\bInfosys\s*Nifty\b"
        ],
        "DOWJONES": [
            r"\bDow\s*Jones\b", r"\bDow\b(?!\s*Agri)(?!\s*Chemical)", r"\bDJIA\b",
            r"\bDow\s*Industrial\b"
        ],
        "NASDAQ": [
            r"\bNASDAQ\b", r"\bNasdaq\b(?!\s*100)", r"\bNASDAQ-100\b"
        ],
        "SP500": [
            r"\bS&P\s*500\b", r"\bSPX\b", r"\bStandard\s*&\s*Poor's\b",
            r"\bS&P\s*500\s*Index\b"
        ],
        "FTSE": [
            r"\bFTSE\s*100\b", r"\bFTSE\b", r"\bLondon\s*Stock\b",
            r"\bFootsie\b"
        ],
        "DAX": [
            r"\bDAX\b", r"\bGerman\s*Index\b", r"\bXetra\s*DAX\b",
            r"\bDax\b"
        ],
        "NIKKEI": [
            r"\bNikkei\b", r"\bNikkei\s*225\b", r"\bNikkei\s*Index\b",
            r"\bTokyo\s*Exchange\b"
        ],
    }

    COMPANY_SYMBOL_MAP = {
        "reliance": "NIFTY",
        "tata": "NIFTY",
        "infosys": "NIFTY",
        "hdfc": "NIFTY",
        "icici": "NIFTY",
        "sbi": "NIFTY",
        "itc": "NIFTY",
        "lt": "NIFTY",
        "sbin": "NIFTY",
        "hindustan": "NIFTY",
        "hdfc bank": "BANKNIFTY",
        "icici bank": "BANKNIFTY",
        "sbi bank": "BANKNIFTY",
        "kotak": "BANKNIFTY",
        "axis bank": "BANKNIFTY",
        "apple": "NASDAQ",
        "microsoft": "NASDAQ",
        "amazon": "NASDAQ",
        "google": "NASDAQ",
        "meta": "NASDAQ",
        "tesla": "NASDAQ",
        "nvidia": "NASDAQ",
        "netflix": "NASDAQ",
    }

    def __init__(self):
        self._compiled_patterns = {}
        self._compile_patterns()

    def _compile_patterns(self):
        for symbol, patterns in self.SYMBOL_PATTERNS.items():
            self._compiled_patterns[symbol] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

    def extract_symbols(self, text: str) -> list[str]:
        if not text:
            return []

        found_symbols = set()

        for symbol, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(text):
                    found_symbols.add(symbol)
                    break

        text_lower = text.lower()
        for company, symbol in self.COMPANY_SYMBOL_MAP.items():
            if company in text_lower and symbol not in found_symbols:
                found_symbols.add(symbol)

        for supported in SUPPORTED_SYMBOLS:
            if supported in text and supported not in found_symbols:
                found_symbols.add(supported)

        return list(found_symbols)

    def extract_symbols_with_confidence(self, text: str) -> list[dict]:
        if not text:
            return []

        results = []

        for symbol, patterns in self._compiled_patterns.items():
            confidence = 0.0
            matched = False
            for pattern in patterns:
                matches = pattern.findall(text)
                if matches:
                    confidence = max(confidence, 0.7)
                    matched = True

            if matched:
                results.append({
                    "symbol": symbol,
                    "confidence": confidence,
                })

        text_lower = text.lower()
        for company, symbol in self.COMPANY_SYMBOL_MAP.items():
            if company in text_lower:
                existing = next((r for r in results if r["symbol"] == symbol), None)
                if existing:
                    existing["confidence"] = max(existing["confidence"], 0.5)
                else:
                    results.append({
                        "symbol": symbol,
                        "confidence": 0.4,
                    })

        results.sort(key=lambda x: x["confidence"], reverse=True)

        return results


entity_mapper = EntityMapper()
