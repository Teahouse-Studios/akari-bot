class Bot:
    @staticmethod
    def bind_template(template):
        for x in template.all_func:
            setattr(Bot, x, getattr(template, x))

    @staticmethod
    def fetch_target(targetId):
        ...
