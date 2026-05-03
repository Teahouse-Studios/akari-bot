from core.builtins.session.features import Features as FeaturesBase


class Features(FeaturesBase):
    image = True
    voice = True
    mention = True
    embed = False
    forward = True
    delete = True
    manage = True
    markdown = False
    reaction = True
    quote = True
    rss = True
    typing = True
    wait = True
