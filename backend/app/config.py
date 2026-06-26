from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql://retailiq:retailiq_secret@db:5432/retailiq"

    # Census
    census_api_key: str = ""

    # Target city
    city_name: str = "Austin"
    city_state: str = "TX"
    city_state_fips: str = "48"
    city_county_fips: str = "453"
    city_bbox: str = "-97.9383,30.0982,-97.4109,30.5283"

    # OSM
    overpass_url: str = "https://overpass-api.de/api/interpreter"

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    @property
    def bbox_tuple(self) -> tuple[float, float, float, float]:
        """Returns (lon_min, lat_min, lon_max, lat_max) as floats."""
        parts = [float(x.strip()) for x in self.city_bbox.split(",")]
        return tuple(parts)  # type: ignore[return-value]

    @property
    def census_base_url(self) -> str:
        return "https://api.census.gov/data"

    @property
    def tiger_base_url(self) -> str:
        return "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb"


@lru_cache
def get_settings() -> Settings:
    return Settings()
