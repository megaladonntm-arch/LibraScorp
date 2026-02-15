from dataclasses import dataclass


@dataclass
class Settings:
    bot_token: str
    admin_id: int
    default_tokens: int


def load_settings() -> Settings:
    return Settings(
        bot_token="8205057314:AAHEys2swVTL7yG83b70Jx5a1_V2FJTsTgg",
        admin_id=5110836226,
        default_tokens=10,
    )
