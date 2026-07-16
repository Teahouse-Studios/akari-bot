from core.config import Config
from core.utils.http import url_pattern

enable_send_url = Config("qq_bot_enable_send_url", False, table_name="bot_qqbot")


def url_filter(msg: str):
    filtered_msg = []
    lines = msg.split("\n")
    for line in lines:
        if enable_send_url:

            def process_url(match):
                url_ = match.group(0)
                parts = url_.split(".")
                for i in range(1, len(parts)):
                    if parts[i] and parts[i][0].isalpha():
                        parts[i] = parts[i][0].upper() + parts[i][1:]
                return ".".join(parts)

            line = url_pattern.sub(process_url, line)
        elif url_pattern.findall(line):
            continue
        filtered_msg.append(line)
    return "\n".join(filtered_msg).strip()
