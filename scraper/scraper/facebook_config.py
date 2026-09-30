"""Session-cookies til Facebook Marketplace (kun sources/facebook.py).

Holdt separat fra scraper_core.config.Settings med vilje, af samme grund som
vacuum_config.py: den delte klasse dækker kun framework-niveau env-vars
fælles for alle projekter på denne boilerplate. En Facebook-login-session er
noget helt andet -- en KONTOSPECIFIK hemmelighed, kun relevant for netop
denne kilde -- og hører derfor til her, i selve vacuum-projektet.

c_user + xs er de to cookies der tilsammen udgør en gyldig Facebook-login-
session (verificeret 2026-09-30 mod en brugerens egen, dedikerede Firefox-
profil -- IKKE deres primære konto, se sources/facebook.py's docstring for
den fulde risikoafvejning). Ingen holdbarhedsgaranti: Facebook kan udløbe
eller spærre sessionen uden varsel.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FacebookSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    facebook_c_user: str | None = Field(default=None, alias="FACEBOOK_C_USER")
    facebook_xs: str | None = Field(default=None, alias="FACEBOOK_XS")

    @property
    def configured(self) -> bool:
        return bool(self.facebook_c_user and self.facebook_xs)


def get_facebook_settings() -> FacebookSettings:
    """Lille indirektion, samme mønster som scraper_core.config.get_settings()
    -- gør det nemt at monkeypatche i tests."""
    return FacebookSettings()
