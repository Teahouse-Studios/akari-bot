unsafe_word_list = [
    "geoip",
    "ip",
]

warning_word_list = [
    "location",
]

unsafe_prompt_list = [
    "where am i",
    "where i am",
    "who am i",
    "who i am",
]


async def secret_check(query):
    query = query.lower()

    for word in warning_word_list:
        if word in query.split() and len(query.split()) > 1:
            return True

    for word in unsafe_word_list:
        if word in query:
            index = query.find(word)
            if (index == 0 or not query[index - 1].isalpha()) and \
               (index + len(word) == len(query) or not query[index + len(word)].isalpha()):
                return True

    for prompt in unsafe_prompt_list:
        if prompt in query:
            return True

    return False
