"""Speech normalization and presentation configuration, without word-budget enforcement."""
import re
from datetime import date
from enum import Enum

from num2words import num2words
from app.prompts import DEFAULT_PROMPTS, render_template


class ResponseMode(str, Enum):
    TEXT = "text"
    SPEECH = "speech"


SPEECH_MAX_WORDS = 60

SPEECH_STYLE_PROMPT = render_template(DEFAULT_PROMPTS.speech_style, max_words=str(SPEECH_MAX_WORDS))
MONTHS = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")


def _number(value: str) -> str:
    try:
        return num2words(int(value), lang="pt_BR")
    except (ValueError, OverflowError):
        return " ".join(num2words(int(d), lang="pt_BR") for d in value if d.isdigit())


def normalize_speech(text: str) -> str:
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"(?m)^[ \t]*(?:#{1,6}[ \t]+|>[ \t]*|[-*+][ \t]+|\d+[.)][ \t]+)", "", text)
    text = re.sub(r"[*_`|]", "", text)
    # Paragraph boundaries must not join two unpunctuated sentences together.
    text = re.sub(r"([^\s.!?…:;])\s*\n[ \t]*\n+\s*", r"\1. ", text)
    def expand_money(match):
        units = int(match[1].replace(".", ""))
        cents = int((match[2] or "0").ljust(2, "0"))
        result = f"{_number(str(units))} {'real' if units == 1 else 'reais'}"
        if cents:
            result += f" e {_number(str(cents))} {'centavo' if cents == 1 else 'centavos'}"
        return result
    text = re.sub(r"R\$\s*(\d+(?:\.\d{3})*)(?:,(\d{1,2}))?", expand_money, text)
    def expand_date(match):
        d, m, y = map(int, match.groups())
        try:
            date(y, m, d)
        except ValueError:
            return match.group(0)
        day = "primeiro" if d == 1 else _number(str(d))
        return f"{day} de {MONTHS[m - 1]} de {_number(str(y))}"
    text = re.sub(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", expand_date, text)
    text = re.sub(r"\bàs\s+(?=0?1:\d{2}\b|uma hora\b)", lambda m: "À " if m[0][0].isupper() else "à ", text, flags=re.I)
    def expand_time(match):
        hours, minutes = map(int, match.groups())
        hour_number = _number(str(hours))
        if hours in (2, 22):
            hour_number = hour_number.removesuffix("dois") + "duas"
        elif hours == 21:
            hour_number = hour_number.removesuffix("um") + "uma"
        spoken = "uma hora" if hours == 1 else f"{hour_number} horas"
        if minutes:
            spoken += " e um minuto" if minutes == 1 else f" e {_number(str(minutes))} minutos"
        return spoken
    text = re.sub(r"\b(\d{1,2}):(\d{2})\b", expand_time, text)
    text = re.sub(r"(?<=\d)\.(?=\d{3}(?:\D|$))", "", text)
    text = re.sub(r"\b(\d+),(\d+)\b", lambda m: f"{_number(m[1])} vírgula " + " ".join(_number(d) for d in m[2]), text)
    text = re.sub(r"(?<!\w)-?\d+(?!\w)", lambda m: _number(m[0]), text)
    text = text.replace("%", " por cento").replace("R$", " reais ")
    text = re.sub(r"\bIFPR\b", "Instituto Federal do Paraná", text, flags=re.I)
    text = re.sub(r"\b(?:km|kg)\b", lambda m: {"km": "quilômetros", "kg": "quilogramas"}[m[0]], text)
    return " ".join(text.split()).strip()
