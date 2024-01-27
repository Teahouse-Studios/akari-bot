unsafe_word_list = [
                "ip",
                "where am i",
                "where i am",
                ]

async def safe_check(query):
    for word in unsafe_word_list:
        if word in query.lower():
            return False
    return True