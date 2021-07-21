class Template:
    __slots__ = ("sendMessage", "waitConfirm", "checkPermission", "revokeMessage", 'asDisplay')

    @classmethod
    def bind_template(self, template):
        for x in template.all_func:
            setattr(Template, x, getattr(template(), x))
