"""Weather value object with locale-aware advice text."""
from __future__ import annotations

from dataclasses import dataclass

from ..core import i18n

RAIN_CODES = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 71, 73, 75, 77, 80, 81, 82, 95, 96, 99}
SNOW_CODES = {71, 73, 75, 77, 85, 86}


@dataclass
class Weather:
    date: str
    temp_max: float | None = None
    precipitation_probability: int | None = None
    weathercode: int | None = None
    available: bool = True
    stale: bool = False

    @property
    def is_rainy(self) -> bool:
        return (self.weathercode in RAIN_CODES
                or (self.precipitation_probability or 0) >= 60)

    def advice(self, language: str | None = None) -> str:
        if not self.available:
            return i18n.t("weather_unavailable", language)
        key = "weather_rain" if self.is_rainy else "weather_dry"
        return i18n.t(
            key, language,
            date=self.date,
            probability=self.precipitation_probability if self.precipitation_probability is not None else 0,
            temp=self.temp_max if self.temp_max is not None else "—",
        )

    def to_cache(self) -> dict:
        return {
            "date": self.date,
            "temp_max": self.temp_max,
            "precipitation_probability": self.precipitation_probability,
            "weathercode": self.weathercode,
        }

    @classmethod
    def from_cache(cls, data: dict, *, stale: bool = False) -> "Weather":
        return cls(
            date=str(data.get("date", "")),
            temp_max=data.get("temp_max"),
            precipitation_probability=data.get("precipitation_probability"),
            weathercode=data.get("weathercode"),
            available=True,
            stale=stale,
        )
