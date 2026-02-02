from core.builtins.session.features import Features as FeaturesBase


class Features(FeaturesBase):
    image = True
    voice = True
    mention = True
    embed = True
    forward = False
    delete = True
    manage = True
    markdown = True
    reaction = True
    quote = True
    rss = True
    typing = True
    wait = True
