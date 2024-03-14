unsafe_word_list = [
    "ip",
    "geoip",
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
    for prompt in unsafe_prompt_list:
        if prompt in query:
            return True

    for word in unsafe_word_list:
        if word in query:
            index = query.find(word)
            if (index == 0 or not query[index - 1].isalpha()) and \
               (index + len(word) == len(query) or not query[index + len(word)].isalpha()):
                return True
    return False
