from core.builtins.session.features import Features as FeaturesBase


class Features(FeaturesBase):
    image = True
    voice = False
    mention = True
    embed = False
    forward = False
    delete = True
    markdown = False
    reaction = True
    quote = True
    rss = False
    typing = False
    wait = False
