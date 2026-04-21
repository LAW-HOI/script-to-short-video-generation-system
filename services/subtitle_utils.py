from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class SrtBlock:
    index: int
    start: float
    end: float
    text: str


def detect_text_language(text: str) -> str:
    latin_letters = len(re.findall(r"[A-Za-z]", text))
    cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    english_words = len(re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", text))
    if english_words >= 3 and latin_letters >= cjk_chars:
        return "en"
    if cjk_chars > latin_letters:
        return "zh"
    return "en" if latin_letters else "zh"


def split_script_text(script: str, max_chars: int, language: str | None = None) -> list[str]:
    normalized = clean_script_text(script).replace("\r\n", "\n").strip()
    if not normalized:
        return []
    resolved_language = language or detect_text_language(normalized)
    if resolved_language == "en":
        return split_english_text(normalized, max_chars)
    return split_chinese_text(normalized, max_chars)


def clean_script_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def split_chinese_text(script: str, max_chars: int) -> list[str]:
    # Chinese subtitles read more naturally when we preserve punctuation-based pauses
    # and only force character-level splitting as a last resort.
    chunks: list[str] = []
    current = ""
    paragraphs = [item.strip() for item in script.split("\n") if item.strip()]
    for paragraph in paragraphs:
        for sentence in split_chinese_sentences(paragraph):
            for clause in split_chinese_clauses(sentence, max_chars):
                clause = clause.strip()
                if not clause:
                    continue
                if not current:
                    current = clause
                    continue
                candidate = f"{current}{clause}" if len(current) + len(clause) <= max_chars else ""
                if candidate:
                    current = candidate
                    continue
                chunks.append(current.strip())
                current = clause
    if current:
        chunks.append(current.strip())
    return chunks


def split_english_text(script: str, max_chars: int) -> list[str]:
    # English subtitles should be split by sentence -> clause -> words,
    # instead of raw characters, otherwise words get torn apart visually.
    chunks: list[str] = []
    current = ""
    paragraphs = [item.strip() for item in script.split("\n") if item.strip()]
    for paragraph in paragraphs:
        for sentence in split_english_sentences(paragraph):
            for clause in split_english_clause(sentence, max_chars):
                clause = clause.strip()
                if not clause:
                    continue
                if not current:
                    current = clause
                    continue
                candidate = f"{current} {clause}".strip()
                if subtitle_display_width(candidate, "en") <= max_chars:
                    current = candidate
                    continue
                chunks.append(current.strip())
                current = clause
    if current:
        chunks.append(current.strip())
    return chunks


def split_chinese_sentences(paragraph: str) -> list[str]:
    parts = re.split(r"(?<=[。！？!?；;])", paragraph)
    return [item.strip() for item in parts if item.strip()]


def split_chinese_clauses(sentence: str, max_chars: int) -> list[str]:
    if subtitle_display_width(sentence, "zh") <= max_chars:
        return [sentence]
    parts = re.split(r"(?<=[，、：,:])", sentence)
    compact_parts = [item.strip() for item in parts if item.strip()]
    if len(compact_parts) <= 1:
        return force_split_chinese(sentence, max_chars)
    chunks: list[str] = []
    current = ""
    for part in compact_parts:
        candidate = f"{current}{part}" if current else part
        if subtitle_display_width(candidate, "zh") <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            if subtitle_display_width(part, "zh") <= max_chars:
                current = part
            else:
                forced = force_split_chinese(part, max_chars)
                chunks.extend(forced[:-1])
                current = forced[-1]
    if current:
        chunks.append(current.strip())
    return chunks


def force_split_chinese(text: str, max_chars: int) -> list[str]:
    compact = text.strip()
    if not compact:
        return []
    pieces: list[str] = []
    buffer = ""
    for char in compact:
        candidate = f"{buffer}{char}"
        if subtitle_display_width(candidate, "zh") <= max_chars or not buffer:
            buffer = candidate
        else:
            pieces.append(buffer.strip())
            buffer = char
    if buffer:
        pieces.append(buffer.strip())
    return pieces


def split_english_sentences(paragraph: str) -> list[str]:
    parts = re.split(r"(?<=[.!?;])\s+", paragraph)
    return [item.strip() for item in parts if item.strip()]


def split_english_clause(sentence: str, max_chars: int) -> list[str]:
    if subtitle_display_width(sentence, "en") <= max_chars:
        return [sentence]
    chunks: list[str] = []
    comma_parts = re.split(r"(?<=[,:;])\s+", sentence)
    if len(comma_parts) > 1:
        current = ""
        for part in comma_parts:
            part = part.strip()
            if not part:
                continue
            candidate = f"{current} {part}".strip() if current else part
            if subtitle_display_width(candidate, "en") <= max_chars:
                current = candidate
            else:
                if current:
                    chunks.append(current.strip())
                current = part
        if current:
            chunks.append(current.strip())
    else:
        chunks = []
    final_chunks: list[str] = []
    for chunk in chunks or [sentence]:
        if subtitle_display_width(chunk, "en") <= max_chars:
            final_chunks.append(chunk.strip())
        else:
            final_chunks.extend(force_split_english(chunk, max_chars))
    return [item for item in final_chunks if item]


def force_split_english(text: str, max_chars: int) -> list[str]:
    words = re.findall(r"\S+", text.strip())
    if not words:
        return []
    chunks: list[str] = []
    current = ""
    for word in words:
        if subtitle_display_width(word, "en") > max_chars and not current:
            split_words = break_long_english_token(word, max_chars)
            chunks.extend(split_words[:-1])
            current = split_words[-1]
            continue
        candidate = f"{current} {word}".strip() if current else word
        if subtitle_display_width(candidate, "en") <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            if subtitle_display_width(word, "en") <= max_chars:
                current = word
            else:
                split_words = break_long_english_token(word, max_chars)
                chunks.extend(split_words[:-1])
                current = split_words[-1]
    if current:
        chunks.append(current.strip())
    return chunks


def break_long_english_token(token: str, max_chars: int) -> list[str]:
    if len(token) <= max_chars:
        return [token]
    parts: list[str] = []
    current = token
    while len(current) > max_chars:
        cut = current.rfind("-", 0, max_chars + 1)
        if cut <= 1:
            cut = max_chars
        parts.append(current[:cut].strip())
        current = current[cut:].lstrip("-")
    if current:
        parts.append(current.strip())
    return [item for item in parts if item]


def subtitle_display_width(text: str, language: str | None = None) -> int:
    # We use an approximate display width rather than raw string length so that
    # English timing and line wrapping are based on word density, not letters.
    resolved_language = language or detect_text_language(text)
    if resolved_language == "en":
        words = re.findall(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*", text)
        punctuation = re.findall(r"[.,!?;:]", text)
        return len(words) * 4 + len(punctuation)
    return len(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", text)) + len(re.findall(r"[，。！？；、,:.!?;]", text))


def subtitle_weight(text: str, language: str | None = None) -> int:
    resolved_language = language or detect_text_language(text)
    if resolved_language == "en":
        return max(len(re.findall(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*", text)), 1)
    return max(len(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", text)), 1)


def format_srt_timestamp(seconds: float) -> str:
    milliseconds = int(round(max(seconds, 0) * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def parse_srt_timestamp(value: str) -> float:
    hours, minutes, rest = value.strip().split(":")
    seconds, milliseconds = rest.split(",")
    total = (
        int(hours) * 3600
        + int(minutes) * 60
        + int(seconds)
        + int(milliseconds) / 1000
    )
    return float(total)


def parse_srt_blocks(content: str) -> list[SrtBlock]:
    blocks: list[SrtBlock] = []
    raw_blocks = re.split(r"\n\s*\n", content.strip(), flags=re.MULTILINE)
    for raw_block in raw_blocks:
        lines = [line.rstrip() for line in raw_block.splitlines() if line.strip()]
        if len(lines) < 2 or " --> " not in lines[1]:
            continue
        try:
            index = int(lines[0].strip())
        except ValueError:
            index = len(blocks) + 1
        start_text, end_text = lines[1].split(" --> ", 1)
        text = "\n".join(lines[2:]).strip()
        if not text:
            continue
        blocks.append(
            SrtBlock(
                index=index,
                start=parse_srt_timestamp(start_text),
                end=parse_srt_timestamp(end_text),
                text=text,
            )
        )
    return blocks


def render_srt_blocks(blocks: list[SrtBlock]) -> str:
    entries: list[str] = []
    for index, block in enumerate(blocks, start=1):
        entries.append(
            f"{index}\n"
            f"{format_srt_timestamp(block.start)} --> {format_srt_timestamp(block.end)}\n"
            f"{block.text.strip()}\n"
        )
    return "\n".join(entries) + "\n"
