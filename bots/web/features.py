from core.builtins.session.features import Features as FeaturesBase


class Features(FeaturesBase):
    image = True
    voice = False
    mention = False
    embed = False
    forward = False
    delete = True
    manage = False
    markdown = True
    reaction = True
    quote = False
    rss = False
    typing = True
    wait = True
