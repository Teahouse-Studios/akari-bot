from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import ImageElement
from core.builtins.message.internal import Image, Plain, I18NContext
from core.component import module

from PIL import Image as PILImage


image = module("image", developers=["OasisAkari"], required_superuser=True)
# only superusers now due to indeterminate safety


@image.command("fillwhite ...")  # convert picture with transparent background to white background image
async def fillwhite(msg: Bot.MessageSession):
    imgs = [e for e in msg.session_info.messages.values if isinstance(e, ImageElement)]
    if not imgs:
        nm = await msg.wait_next_message(I18NContext("image.fillwhite.send.a.image"))
        nm_image = [e for e in nm.session_info.messages.values if isinstance(e, ImageElement)]
        if not nm_image:
            await msg.finish(I18NContext("image.fillwhite.no.image.found"))
        imgs = nm_image
    converted_imgs = []
    i = 1
    for img in imgs:
        get_img = await img.to_PIL_image()
        if len(imgs) > 1:
            converted_imgs.append(Plain(str(i) + "."))
        if get_img.mode in ("RGBA", "LA") or (get_img.mode == "P" and "transparency" in get_img.info):
            background = PILImage.new("RGBA", get_img.size, (255, 255, 255))
            background.alpha_composite(get_img.convert("RGBA"))
            get_img = background

            converted_imgs.append(Image(get_img))
        else:
            converted_imgs.append(I18NContext("image.fillwhite.cannot.detect.alpha.channel"))
        i += 1
    await msg.finish(MessageChain.assign(converted_imgs))
