from enum import Enum


class Language(str, Enum):
    english = "en"
    polish = "pl"
    german = "de"
    spanish = "es"


LANGUAGE_NAMES: dict["Language", str] = {
    Language.english: "English",
    Language.polish: "Polish",
    Language.german: "German",
    Language.spanish: "Spanish",
}
