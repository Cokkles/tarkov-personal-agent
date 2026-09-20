from __future__ import annotations

import re
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from tarkov_voice.types import Hit, Word

_PUNCT = re.compile(r"[^a-z0-9\- ]+")

# Spoken letter sequences that ASR often writes out instead of "pmc".
_SPOKEN_ABBREVIATIONS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("p", "m", "c"), "pmc"),
    (("p", "m", "cs"), "pmcs"),
    (("pee", "em", "see"), "pmc"),
    (("pee", "em", "sees"), "pmcs"),
    (("p", "m", "see"), "pmc"),
)

# Words that end an item name: "found a keycard in the office" -> "keycard".
_ITEM_STOP_WORDS = {
    "in", "on", "at", "from", "near", "behind", "inside", "under", "next", "by", "with",
    "and", "but", "so", "because", "which", "that", "while", "when",
}

_TRAILING_FILLER = {
    "and", "so", "but", "now", "here", "in", "on", "at", "from", "for", "just", "then",
    "there", "right", "like", "um", "uh", "with", "to", "of",
}


@dataclass(slots=True)
class Rule:
    name: str
    marker_type: str
    confidence: float
    prefix_confidence: float
    cooldown_s: float
    patterns: list[re.Pattern[str]] = field(default_factory=list)
    prefix_aliases: list[re.Pattern[str]] = field(default_factory=list)


@dataclass(slots=True)
class _Token:
    text: str
    start: float
    end: float
    raw: str
    sentence_end: bool


@dataclass(slots=True)
class Settings:
    negative_context: list[re.Pattern[str]]
    negative_multiplier: float
    prefix_fillers: set[str]
    important_loot: list[re.Pattern[str]]
    important_loot_boost: float
    loot_stoplist: list[str]
    loot_reject_words: set[str]


def normalize_word(raw: str) -> str:
    text = raw.lower().replace("’", "'").replace("'", "")
    return _PUNCT.sub("", text).strip()


def _collapse(tokens: list[_Token]) -> list[_Token]:
    """Merge spoken letters ("p m c") into one token so patterns can match "pmc"."""
    out: list[_Token] = []
    index = 0
    while index < len(tokens):
        merged = False
        for letters, replacement in _SPOKEN_ABBREVIATIONS:
            width = len(letters)
            window = tokens[index : index + width]
            if len(window) == width and tuple(t.text for t in window) == letters:
                out.append(
                    _Token(
                        text=replacement,
                        start=window[0].start,
                        end=window[-1].end,
                        raw=" ".join(t.raw for t in window),
                        sentence_end=window[-1].sentence_end,
                    )
                )
                index += width
                merged = True
                break
        if not merged:
            out.append(tokens[index])
            index += 1
    return out


def _tokenize(words: Sequence[Word]) -> list[_Token]:
    tokens: list[_Token] = []
    for word in words:
        text = normalize_word(word.text)
        if not text:
            continue
        # A hyphenated word like "well-timed" stays one token.
        tokens.append(
            _Token(
                text=text,
                start=word.start,
                end=word.end,
                raw=word.text.strip(),
                sentence_end=word.text.rstrip().endswith((".", "?", "!")),
            )
        )
    return _collapse(tokens)


def _split_sentences(tokens: list[_Token]) -> list[list[_Token]]:
    sentences: list[list[_Token]] = []
    current: list[_Token] = []
    for token in tokens:
        current.append(token)
        if token.sentence_end:
            sentences.append(current)
            current = []
    if current:
        sentences.append(current)
    return sentences


def _phrase_regex(term: str) -> re.Pattern[str]:
    return re.compile(rf"\b{re.escape(term)}\b")


def load_rules(path: Path) -> tuple[list[Rule], Settings]:
    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    section = raw.get("settings", {})
    settings = Settings(
        negative_context=[_phrase_regex(t) for t in section.get("negative_context", [])],
        negative_multiplier=float(section.get("negative_multiplier", 0.5)),
        prefix_fillers=set(section.get("prefix_fillers", [])),
        important_loot=[_phrase_regex(t) for t in section.get("important_loot", [])],
        important_loot_boost=float(section.get("important_loot_boost", 0.15)),
        loot_stoplist=[str(t) for t in section.get("loot_item_stoplist", [])],
        loot_reject_words=set(
            section.get(
                "loot_reject_words",
                [
                    "guy", "guys", "pmc", "scav", "player", "kill", "killed", "shot", "hit",
                    "eyes", "visual", "hurt", "feeling", "idea", "problem", "message", "chat",
                    "subscriber", "follower", "sub", "donation", "bits", "raid", "extract",
                    "spawn", "death", "killa", "dead",
                ],
            )
        ),
    )

    rules: list[Rule] = []
    for entry in raw.get("rule", []):
        rules.append(
            Rule(
                name=str(entry["name"]),
                marker_type=str(entry["marker_type"]),
                confidence=float(entry.get("confidence", 0.7)),
                prefix_confidence=float(entry.get("prefix_confidence", 0.95)),
                cooldown_s=float(entry.get("cooldown_s", 6.0)),
                patterns=[re.compile(p) for p in entry.get("patterns", [])],
                prefix_aliases=[re.compile(p) for p in entry.get("prefix_aliases", [])],
            )
        )
    return rules, settings


class TriggerEngine:
    """Finds marker callouts in word-timestamped transcripts.

    Hits carry the time the phrase began, not the time transcription finished, so the
    marker lands on the right frame of the recording.
    """

    def __init__(
        self,
        rules: list[Rule],
        settings: Settings,
        *,
        mode: str = "hybrid",
        min_confidence: float = 0.5,
        prefix_words: Sequence[str] = ("mark", "marker", "tag"),
    ) -> None:
        if mode not in {"hybrid", "prefix_only"}:
            raise ValueError(f"Unknown trigger mode: {mode}")
        self._rules = rules
        self._settings = settings
        self._mode = mode
        self._min_confidence = min_confidence
        self._prefix_words = {w.lower() for w in prefix_words}
        self._last_fired: dict[tuple[str, str], float] = {}
        self._pending_prefix_until: float = 0.0

    @classmethod
    def from_file(
        cls,
        path: Path,
        *,
        mode: str = "hybrid",
        min_confidence: float = 0.5,
        prefix_words: Sequence[str] = ("mark", "marker", "tag"),
    ) -> TriggerEngine:
        rules, settings = load_rules(path)
        return cls(
            rules,
            settings,
            mode=mode,
            min_confidence=min_confidence,
            prefix_words=prefix_words,
        )

    def reset(self) -> None:
        self._last_fired.clear()
        self._pending_prefix_until = 0.0

    # ------------------------------------------------------------------ public

    def scan(self, words: Sequence[Word]) -> list[Hit]:
        hits: list[Hit] = []
        for sentence in _split_sentences(_tokenize(words)):
            hits.extend(self._scan_sentence(sentence))
        return hits

    # ---------------------------------------------------------------- internals

    def _scan_sentence(self, sentence: list[_Token]) -> list[Hit]:
        if not sentence:
            return []

        snippet = " ".join(t.raw for t in sentence)[:300]
        start_index = 0
        while (
            start_index < len(sentence)
            and sentence[start_index].text in self._settings.prefix_fillers
        ):
            start_index += 1

        prefixed = False
        prefix_time = sentence[0].start
        body_tokens = sentence

        if start_index < len(sentence) and sentence[start_index].text in self._prefix_words:
            prefixed = True
            prefix_time = sentence[start_index].start
            body_tokens = sentence[start_index + 1 :]
            if not body_tokens:
                # "Mark." on its own: the callout is probably the next sentence.
                self._pending_prefix_until = sentence[-1].end + 4.0
                return []
        elif sentence[0].start <= self._pending_prefix_until:
            prefixed = True
            prefix_time = sentence[0].start
            self._pending_prefix_until = 0.0

        if not body_tokens:
            return []

        if prefixed:
            return self._prefixed_hits(body_tokens, prefix_time, snippet)
        if self._mode == "prefix_only":
            return []
        return self._natural_hits(sentence, snippet)

    def _joined(self, tokens: list[_Token]) -> tuple[str, list[int]]:
        """Join tokens with spaces and map each character offset to its token index."""
        parts: list[str] = []
        offsets: list[int] = []
        for index, token in enumerate(tokens):
            parts.append(token.text)
            offsets.extend([index] * (len(token.text) + 1))
        return " ".join(parts), offsets

    def _natural_hits(self, tokens: list[_Token], snippet: str) -> list[Hit]:
        text, offsets = self._joined(tokens)
        multiplier = (
            self._settings.negative_multiplier
            if any(p.search(text) for p in self._settings.negative_context)
            else 1.0
        )
        hits: list[Hit] = []
        for rule in self._rules:
            for pattern in rule.patterns:
                match = pattern.search(text)
                if match is None:
                    continue
                hit = self._build_hit(
                    rule,
                    match,
                    tokens,
                    offsets,
                    base_confidence=rule.confidence * multiplier,
                    snippet=snippet,
                    prefixed=False,
                )
                if hit is not None:
                    hits.append(hit)
                    break
        return self._filter(self._resolve_conflicts(hits))

    @staticmethod
    def _resolve_conflicts(hits: list[Hit]) -> list[Hit]:
        """"there's a guy on the roof" reads as both heard and seen; keep the specific one."""
        kinds = {h.marker_type for h in hits}
        if "contact.visual.player" in kinds and "contact.audio.possible_pmc" in kinds:
            return [h for h in hits if h.marker_type != "contact.audio.possible_pmc"]
        return hits

    def _prefixed_hits(
        self,
        body: list[_Token],
        prefix_time: float,
        snippet: str,
    ) -> list[Hit]:
        text, offsets = self._joined(body)
        hits: list[Hit] = []

        if text.startswith("note ") or text == "note":
            note = text[5:].strip()
            if note:
                hits.append(
                    Hit(
                        marker_type=None,
                        label="Voice note",
                        confidence=0.95,
                        occurred_at=prefix_time,
                        details=f'Voice note: "{note}"',
                        prefixed=True,
                        rule="note",
                    )
                )
            return self._filter(hits)

        for rule in self._rules:
            for pattern in [*rule.prefix_aliases, *rule.patterns]:
                match = pattern.search(text)
                if match is None:
                    continue
                hit = self._build_hit(
                    rule,
                    match,
                    body,
                    offsets,
                    base_confidence=rule.prefix_confidence,
                    snippet=snippet,
                    prefixed=True,
                    time_override=prefix_time,
                )
                if hit is not None:
                    hits.append(hit)
                    break

        if not hits:
            # A prefix word followed by something we do not recognize is still a bookmark.
            hits.append(
                Hit(
                    marker_type=None,
                    label="Voice note",
                    confidence=0.85,
                    occurred_at=prefix_time,
                    details=f'Voice note: "{text}"',
                    prefixed=True,
                    rule="note",
                )
            )
        return self._filter(hits)

    def _build_hit(
        self,
        rule: Rule,
        match: re.Match[str],
        tokens: list[_Token],
        offsets: list[int],
        *,
        base_confidence: float,
        snippet: str,
        prefixed: bool,
        time_override: float | None = None,
    ) -> Hit | None:
        confidence = base_confidence
        details = f'"{snippet}"'
        item = ""

        if "item" in match.groupdict():
            item = self._clean_item(match.group("item") or "")
            if not item and not prefixed and rule.name == "important_loot":
                # "found out that...", "got him": not loot.
                return None
            if item:
                if any(p.search(item) for p in self._settings.important_loot):
                    confidence = min(1.0, confidence + self._settings.important_loot_boost)
                details = f'Found: {item} - "{snippet}"'

        start_char = min(match.start(), len(offsets) - 1)
        token_index = offsets[start_char] if offsets else 0
        occurred_at = (
            time_override if time_override is not None else tokens[token_index].start
        )

        return Hit(
            marker_type=rule.marker_type,
            label="",
            confidence=round(min(1.0, confidence), 3),
            occurred_at=occurred_at,
            details=details[:1000],
            prefixed=prefixed,
            rule=rule.name,
            extra={"item": item} if item else {},
        )

    def _clean_item(self, raw_item: str) -> str:
        words = raw_item.split()
        for position, word in enumerate(words):
            if position > 0 and word in _ITEM_STOP_WORDS:
                words = words[:position]
                break
        while words and words[-1] in _TRAILING_FILLER:
            words.pop()
        item = " ".join(words)
        if not item:
            return ""
        for stop in self._settings.loot_stoplist:
            if item == stop or item.startswith(stop + " "):
                return ""
        if any(word in self._settings.loot_reject_words for word in words):
            return ""
        return item

    def _filter(self, hits: list[Hit]) -> list[Hit]:
        kept: list[Hit] = []
        for hit in hits:
            if hit.confidence < self._min_confidence:
                continue
            if hit.marker_type is not None:
                rule = next((r for r in self._rules if r.name == hit.rule), None)
                cooldown = rule.cooldown_s if rule is not None else 6.0
                key = (hit.marker_type, hit.extra.get("item", ""))
                last = self._last_fired.get(key)
                if last is not None and 0 <= hit.occurred_at - last < cooldown:
                    continue
                self._last_fired[key] = hit.occurred_at
            kept.append(hit)
        return kept
