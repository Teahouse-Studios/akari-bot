from core.builtins.session.features import Features as FeaturesBase


class Features(FeaturesBase):
    image = True
    voice = True
    mention = True
    embed = True
    forward = False
    delete = True
    markdown = True
    quote = True
    rss = True
    typing = True
    wait = True
    reaction = True
