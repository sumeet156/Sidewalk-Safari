"""Weather context is entered by the adult to avoid sending location data anywhere."""


def format_weather_note(weather: str, season: str) -> str:
    weather = weather.strip()
    return f"{weather}; season: {season}" if weather else f"season: {season}"
