import json
from collections import defaultdict

import requests

def get_data_from_api(api_url):
    response = requests.get(api_url)
    if response.status_code == 200:
        return response.json()
    else:
        raise ValueError(f"Failed to fetch data from API: {response.status_code}")

def compress_json(input_data):
    data = input_data["data"]
    known_supported_emoji = input_data["knownSupportedEmoji"]

    compressed_data = {
        "knownSupportedEmoji": known_supported_emoji,
        "data": defaultdict(dict),
        "date": []
    }

    unique_dates = set()

    for emoji_codepoint, emoji_info in data.items():
        combinations = emoji_info["combinations"]
        for left_codepoint, entries in combinations.items():
            for entry in entries:
                date = entry["date"]
                unique_dates.add(date)

    sorted_dates = sorted(unique_dates)

    date_index_map = {date: idx for idx, date in enumerate(sorted_dates)}

    for emoji_codepoint, emoji_info in data.items():
        combinations = emoji_info["combinations"]
        for left_codepoint, entries in combinations.items():
            entries.sort(key=lambda x: x["date"])

            latest_entry = entries[-1]
            left = latest_entry["leftEmojiCodepoint"]
            right = latest_entry["rightEmojiCodepoint"]
            date = latest_entry["date"]

            key = f'({left}, {right})'
            compressed_data["data"][key] = date_index_map[date]

    compressed_data["date"] = sorted_dates

    return compressed_data

if __name__ == "__main__":
    api_url = "https://raw.githubusercontent.com/xsalazar/emoji-kitchen-backend/main/app/metadata.json"
    input_data = get_data_from_api(api_url)
    compressed_data = compress_json(input_data)
    
    with open('output.json', "w", encoding="utf-8") as f:
        json.dump(compressed_data, f, ensure_ascii=False, indent=2)