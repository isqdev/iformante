"""The server, never the model, decides the delivery mode and word budget."""
import re
from datetime import date
from enum import Enum

from num2words import num2words


class ResponseMode(str, Enum):
    TEXT = "text"
    SPEECH = "speech"


SPEECH_MAX_WORDS = 40
SPEECH_FALLBACK = "Não consegui resumir essa resposta com segurança. Pode perguntar sobre um ponto mais específico?"
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
    text = re.sub(r"(?m)^\s*[#>*|\-]+\s*", "", text)
    text = re.sub(r"[*_`|]", "", text)
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
        return f"{_number(str(d))} de {MONTHS[m - 1]} de {_number(str(y))}"
    text = re.sub(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", expand_date, text)
    text = re.sub(r"\b(\d{1,2}):(\d{2})\b", lambda m: f"{_number(m[1])} horas" + (f" e {_number(m[2])} minutos" if int(m[2]) else ""), text)
    text = re.sub(r"(?<=\d)\.(?=\d{3}(?:\D|$))", "", text)
    text = re.sub(r"\b(\d+),(\d+)\b", lambda m: f"{_number(m[1])} vírgula " + " ".join(_number(d) for d in m[2]), text)
    text = re.sub(r"(?<!\w)-?\d+(?!\w)", lambda m: _number(m[0]), text)
    text = text.replace("%", " por cento").replace("R$", " reais ")
    text = re.sub(r"\bIFPR\b", "Instituto Federal do Paraná", text, flags=re.I)
    text = re.sub(r"\b(?:km|kg)\b", lambda m: {"km": "quilômetros", "kg": "quilogramas"}[m[0]], text)
    return " ".join(text.split()).strip()


def within_speech_budget(text: str) -> bool:
    return bool(text.strip()) and len(text.split()) <= SPEECH_MAX_WORDS
