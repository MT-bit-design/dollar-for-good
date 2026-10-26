"""Fetch a web page as plain text, safely. Everything returned here is UNTRUSTED data."""

from __future__ import annotations

import ipaddress
import re
import socket
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app import config

# Charity evaluators the agent may read in addition to the charity's own site.
EVALUATOR_DOMAINS = {
    "givewell.org", "givingwhatwecan.org", "founderspledge.com", "givinggreen.earth",
    "povertyactionlab.org", "poverty-action.org", "thelifeyoucansave.org",
    "animalcharityevaluators.org", "worldbank.org",
}

_ZERO_WIDTH = re.compile(r"[​-‏‪-‮⁠-⁤﻿]")


# Text that is talking to an AI rather than to a human reader.
INJECTION_PATTERNS = [
    r"ignore (all |any |the )?(previous|prior|above|earlier|your) (instructions|rules|prompts?)",
    r"disregard (all |any |the )?(previous|prior|above|your) (instructions|rules)",
    r"\b(system|developer) (prompt|message|instructions?)\b",
    r"\b(ai|llm|language model|chatbot|gpt)s?\b[^.]{0,40}\b(must|should|need to|are instructed to)\b",
    r"\byou are (now )?(an?|the) [a-z ]{0,30}(assistant|agent|model)\b",
    r"\b(reveal|print|show|output)\b[^.]{0,30}\b(api key|prompt|instructions|secret)",
    r"\bnew instructions\b",
]
_INJECTION_RE = [re.compile(p, re.I) for p in INJECTION_PATTERNS]


def detect_injection(text: str) -> list[str]:
    """Return the snippets of text that look like instructions aimed at an AI."""
    hits = []
    for rx in _INJECTION_RE:
        m = rx.search(text)
        if m:
            hits.append(text[max(0, m.start() - 20): m.end() + 20])
    return hits


class FetchError(Exception):
    pass


@dataclass
class Page:
    url: str
    text: str           # cleaned, possibly truncated
    truncated: bool


def registered_domain(host: str) -> str:
    host = host.lower().rstrip(".")
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def is_allowed(url: str, charity_website: str | None) -> tuple[bool, str]:
    """Only http(s), only the charity's own domain or a known evaluator, never private IPs."""
    try:
        u = urlparse(url)
    except ValueError:
        return False, "Not a valid URL."
    if u.scheme not in ("http", "https") or not u.hostname:
        return False, "Only http and https links are allowed."
    if u.username or u.password:
        return False, "Links with a username or password are not allowed."
    host = u.hostname.lower()
    allowed = set(EVALUATOR_DOMAINS)
    if charity_website:
        ch = urlparse(charity_website).hostname
        if ch:
            allowed.add(registered_domain(ch))
    if registered_domain(host) not in allowed:
        return False, f"{host} is not the charity's site or a known evaluator."
    return True, ""


def _host_is_public(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


def clean_text(html: str) -> str:
    """HTML -> visible text. Drops scripts, styles, hidden elements, comments, zero-width chars."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "template", "svg", "iframe", "head"]):
        tag.decompose()
    for tag in soup.find_all(style=re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden", re.I)):
        tag.decompose()
    for tag in soup.find_all(attrs={"hidden": True}):
        tag.decompose()
    for tag in soup.find_all(attrs={"aria-hidden": "true"}):
        tag.decompose()
    text = soup.get_text(" ")
    return normalize(text)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = _ZERO_WIDTH.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_page(url: str, charity_website: str | None = None, *, check_dns: bool = True) -> Page:
    ok, why = is_allowed(url, charity_website)
    if not ok:
        raise FetchError(why)
    host = urlparse(url).hostname or ""
    if check_dns and not _host_is_public(host):
        raise FetchError(f"{host} does not resolve to a public address.")
    headers = {"User-Agent": "CharityImpactTool/1.0 (student project; read-only)"}
    try:
        with httpx.Client(timeout=config.FETCH_TIMEOUT_S, follow_redirects=True,
                          max_redirects=3, headers=headers) as client:
            with client.stream("GET", url) as r:
                # Redirects must stay inside the allowed set too.
                ok, why = is_allowed(str(r.url), charity_website)
                if not ok:
                    raise FetchError(f"Redirected off the allowed sites: {why}")
                if r.status_code >= 400:
                    raise FetchError("The page could not be opened.")
                ctype = r.headers.get("content-type", "")
                if "html" not in ctype and "text" not in ctype:
                    raise FetchError("The link is not a web page.")
                body = b""
                for chunk in r.iter_bytes():
                    body += chunk
                    if len(body) > config.FETCH_MAX_BYTES:
                        break
    except httpx.HTTPError as e:
        raise FetchError("The page could not be reached.") from e
    text = clean_text(body.decode("utf-8", errors="replace"))
    truncated = len(text) > config.PAGE_TEXT_LIMIT
    return Page(url=url, text=text[: config.PAGE_TEXT_LIMIT], truncated=truncated)
