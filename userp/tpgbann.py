# -*- coding: utf-8 -*-
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
def tpgbann(favicon,wikiname,username,gender,registertime,contributionwikis,createcount,editcount,deletecount,patrolcount,sitetop,globaltop,wikipoint,blockbyuser,blocktimestamp1,blocktimestamp2):
    font = ImageFont.truetype('/home/wdljt/oasisakari/bot/assests/SourceHanSansCN-Normal.ttf', 40)
    font1 = ImageFont.truetype('/home/wdljt/oasisakari/bot/assests/SourceHanSansCN-Normal.ttf',70)
    img = Image.open('/home/wdljt/oasisakari/bot/assests/ban.png')
    img2 = Image.open(favicon)
    img3 = Image.new("RGBA", img.size)
    w, h = img2.size
    w = int(w)
    h = int(h)
    try:
        img2 = img2.resize((int(w/(w//100)),int(h/(h//100))))
    except:
        pass
    img3.paste(img,(0,0))

    img21 = Image.new("RGBA",(200,200))
    W = 200
    H = 200
    w,h = img2.size
    img21.alpha_composite(img2.convert("RGBA"),(int((W-w)/2),int((H-h)/2)))

    img3.alpha_composite(img21,(95,52))
    draw = ImageDraw.Draw(img3)
    draw.text((325, 120), str(wikiname), '#ffffff', font=font1)
    draw.text((230, 295), str(username), '#ffffff', font=font1)
    draw.text((617,685),'（UTC+8）','#ffffff',font=font)

    img32 = Image.new("RGBA",(120,40))
    W = 120
    draww = ImageDraw.Draw(img32)
    w, h = draww.textsize(gender,font=font)
    draww.text(((W-w-font.getoffset(gender)[0])/2,0), gender, "#ffffff",font = font)
    img3.alpha_composite(img32,(194,635))

    img31 = Image.new("RGBA", (1280, 40))
    W = 1280
    draww = ImageDraw.Draw(img31)
    w, h = draww.textsize(registertime, font=font)
    draww.text(((W - w - font.getoffset(registertime)[0]) / 2, 0), registertime, "#ffffff", font=font)
    img3.alpha_composite(img31, (80, 635))

    draw.text((800, 785), str(contributionwikis), '#ffffff', font=font)

    img4 = Image.new("RGBA", (280, 40))
    W = 280
    H = 40
    draww = ImageDraw.Draw(img4)
    w, h = draww.textsize(createcount, font=font)
    draww.text(((W - w - font.getoffset(createcount)[0]) / 2, 0), createcount, "#ffffff", font=font)
    img3.alpha_composite(img4, (115, 960))

    img5 = Image.new("RGBA", (280, 40))
    draww = ImageDraw.Draw(img5)
    w, h = draww.textsize(editcount, font=font)
    draww.text(((W - w - font.getoffset(editcount)[0]) / 2, 0), editcount, "#ffffff", font=font)
    img3.alpha_composite(img5, (295, 960))

    img6 = Image.new("RGBA", (280, 40))
    draww = ImageDraw.Draw(img6)
    w, h = draww.textsize(deletecount, font=font)
    draww.text(((W - w - font.getoffset(deletecount)[0]) / 2, 0), deletecount, "#ffffff", font=font)
    img3.alpha_composite(img6, (475, 960))

    img7 = Image.new("RGBA", (280, 40))
    draww = ImageDraw.Draw(img7)
    w, h = draww.textsize(patrolcount, font=font)
    draww.text(((W - w - font.getoffset(patrolcount)[0]) / 2, 0), patrolcount, "#ffffff", font=font)
    img3.alpha_composite(img7, (655, 960))

    img8 = Image.open('/home/wdljt/oasisakari/bot/assests/Blocked.png')
    w,h = img8.size
    w = int(w)
    h = int(h)
    img8 = img8.resize((int(w/1.22),int(h/1.22)))
    img3.alpha_composite(img8.convert("RGBA"),(1,100))

    draw.text((625,1095),str(wikipoint),'#ffffff',font=font)
    draw.text((330, 1195), str(sitetop), '#ffffff', font=font)
    draw.text((690, 1195), str(globaltop), '#ffffff', font=font)
    draw.text((200, 1439), '被' + str(blockbyuser) + '封禁，', '#ffffff', font=font)
    draw.text((200, 1489), '时间从' + str(blocktimestamp1)+'（UTC+8）', '#ffffff', font=font)
    draw.text((200, 1539), '到' + str(blocktimestamp2), '#ffffff', font=font)
    img3.save("/home/wdljt/oasisakari/bot/assests/usercard/"+username+".png")