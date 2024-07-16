import requests

def get_artwork(image_url: str):
    """Gets cover artwork"""
    return requests.get(image_url).content

def sanitize_data(value: str) -> str:
    """Returns given string with problematic removed"""
    sanitizes = ["\\", "/", ":", "*", "?", "'", "<", ">", '"']
    for i in sanitizes:
        value = value.replace(i, "")
    return value.replace("|", "-")