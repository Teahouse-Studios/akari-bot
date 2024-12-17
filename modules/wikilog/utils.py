from typing import Union


def convert_data_to_text(data: Union[dict, list]):
    texts = []
    if isinstance(data, dict):
        for k in data:
            if isinstance(data[k], dict):
                texts.append(f"{k}={{{convert_data_to_text(data[k])}}}")
            elif isinstance(data[k], list):
                texts.append(f"{k}=[{convert_data_to_text(data[k])}]")
            else:
                texts.append(f"{k}={str(data[k])}")
    elif isinstance(data, list):
        for k in data:
            if isinstance(k, (dict, list)):
                texts.append(convert_data_to_text(k))
            else:
                texts.append(str(k))
    return ",".join(texts).replace(" ", "_")
