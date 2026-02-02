from core.builtins.session.features import Features as FeaturesBase


class Features(FeaturesBase):
    image = True
    voice = True
    mention = True
    embed = False
    forward = False
    delete = True
    manage = True
    markdown = False
    reaction = False
    quote = True
    rss = True
    typing = False
    wait = True
