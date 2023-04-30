import discord
import logging as lg
import os
import time
import urllib.request
import uuid
from bing_image_downloader import downloader
from colorsys import rgb_to_hsv, hsv_to_rgb
from colorthief import ColorThief
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance
from typing import List

ANNOUNCEMENT_CH_ID = int(os.getenv('EVENT_ANNOUNCEMENT_CHANNEL_ID'))
EVENTS_FORUM_ID = int(os.getenv('EVENTS_FORUM_ID'))
EVENTS_ROLE_ID = int(os.getenv('EVENTS_ROLE_ID'))

FILE_DIR = os.getenv('FILE_DIR')

# set up static image files
BADGE_FILE = FILE_DIR + "/images/ehv_badge.png"

# set up fonts
SIZE_TITLE = 80
SIZE_TAGS = 48

FONT_TITLE_PATH = FILE_DIR + "/fonts/RobotoFlexVariable.ttf"
FONT_TITLE = ImageFont.truetype(FONT_TITLE_PATH, SIZE_TITLE)
FONT_TITLE.set_variation_by_name('ExtraBlack Italic')

FONT_TAGS_PATH = FILE_DIR + "/fonts/RobotoFlexVariable.ttf"
FONT_TAGS = ImageFont.truetype(FONT_TAGS_PATH, SIZE_TAGS)
FONT_TAGS.set_variation_by_name('Regular')

DESIRED_W = 1230
DESIRED_H = 1400

ALERT = "%s New event added in %s! check it out here: %s"


class Events(commands.Cog):

    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        lg.info(f"[{__name__}] Cog is ready")

    @commands.Cog.listener()
    async def on_thread_create(self, th: discord.Thread):
        f_ch = await th.guild.fetch_channel(EVENTS_FORUM_ID)
        if th.parent_id != EVENTS_FORUM_ID:
            return

        alert_channel = await th.guild.fetch_channel(ANNOUNCEMENT_CH_ID)
        ev_rl = discord.utils.get(th.guild.roles, id=EVENTS_ROLE_ID)
        time.sleep(3)

        img = get_img(th)

        alert_msg = ALERT % (ev_rl.mention, f_ch.mention, th.mention)

        output_img = make_ev_img(img, th.name, th.applied_tags)
        await alert_channel.send(alert_msg, file=discord.File(output_img))

        os.remove(img)
        os.remove(output_img)


def make_ev_img(img_path: str, title: str, tags: List[str]):

    output_img_filename = 'temp/output_%s.png' % uuid.uuid4()

    base_img = Image.new('RGBA', size=(DESIRED_W, DESIRED_H), color=(0,0,0,0))
    badge_img = Image.open(BADGE_FILE)

    colorthief = ColorThief(img_path)
    colors = colorthief.get_palette()

    main_color = next((color for color in colors if not is_dark(color)),
                      (255, 255, 255))
    main_color = adjust_saturation(main_color, -100)
    transparent = (0, 0, 0, 0)
    bubbles_color = (23, 23, 23)

    img = Image.open(img_path).convert('RGB')
    size = img.size

    des_w = DESIRED_W - 80
    des_h = DESIRED_H - 180

    mask_rect = Image.new('L', size=(des_w, des_h), color=0)
    draw = ImageDraw.Draw(mask_rect)
    draw.rounded_rectangle((0, 0, des_w, des_h), radius=40, fill=255)

    border_rect = Image.new('RGBA', size=(des_w, des_h), color=0)
    draw = ImageDraw.Draw(border_rect)
    draw.rounded_rectangle((0, 0, des_w, des_h), radius=40, fill=transparent,
                           outline=main_color, width=10)

    if size[0] < des_w:
        ratio = des_w/size[0]
        size = (round(size[0]*ratio), round(size[1]*ratio))
    if size[1] < des_h:
        ratio = des_h/size[1]
        size = (round(size[0]*ratio), round(size[1]*ratio))

    img = img.resize(size)
    img = crop_img(img)
    img = img.resize((des_w, des_h - 30))
    mask_rect = mask_rect.resize(img.size)
    border_rect = border_rect.resize(img.size)

    base_img.paste(img, (60, 95), mask=mask_rect)
    base_img.paste(border_rect, (60, 95), mask=border_rect)
    base_img = Image.composite(badge_img, base_img, badge_img)
    
    draw_title_text(base_img, title.upper(), 0, 200, DESIRED_W - 20,
                    main_color)
    draw_tag_bubbles(base_img, sorted([tag.name.lower() for tag in tags]),
                     bubbles_color, main_color, FONT_TAGS)
    
    base_img.save(output_img_filename)
    img.close()
    base_img.close()
    badge_img.close()
    os.remove(img_path)

    return output_img_filename


def download_img_from_bing(query):
    temp_folder = "temp/%s" % (uuid.uuid4())
    output_folder = "%s/%s" % (temp_folder, query)
    downloader.download(query, limit=1,  output_dir=temp_folder,
                        adult_filter_off=False, force_replace=False,
                        timeout=60, verbose=False)

    return os.path.join(output_folder, os.listdir(output_folder)[0])


def download_img_from_url(url):
    img_id = uuid.uuid4()
    img_filename = "temp/temp_%s.jpg" % img_id

    opener = urllib.request.build_opener()
    opener.addheaders = [('User-agent', "Mozilla/5.0 (Windows NT 6.1)")]

    urllib.request.install_opener(opener)
    urllib.request.urlretrieve(url, img_filename)

    return img_filename


def is_dark(color):
    red = color[0]
    green = color[1]
    blue = color[2]
    darkness = 1.0-(0.299*red + 0.587*green + 0.114*blue)/255.0

    return darkness > 0.5


def get_img(thread: discord.Thread):
    time.sleep(1)
    msg = thread.starter_message
    if msg.attachments:
        return download_img_from_url(msg.attachments[0].url)
    if msg.embeds:
        for embed in msg.embeds:
            if embed.thumbnail:
                return download_img_from_url(embed.thumbnail.url)
    return download_img_from_bing(thread.name)


def complementary(inp):
    hsv = rgb_to_hsv(inp[0], inp[1], inp[2])
    rgb = hsv_to_rgb((hsv[0] + 0.5) % 1, hsv[1], hsv[2])
    return tuple(int(x) for x in rgb)


def adjust_saturation(inp, val):
    hsv = rgb_to_hsv(inp[0], inp[1], inp[2])
    hsv = (hsv[0], min(hsv[1]*((100+val)/100), 1), hsv[2])
    rgb = hsv_to_rgb(hsv[0], hsv[1], hsv[2])
    return tuple(int(x) for x in rgb)


def adjust_darkness(inp, val):
    hsv = rgb_to_hsv(inp[0], inp[1], inp[2])
    hsv = (hsv[0], hsv[1], hsv[2]*(1-(val/100.0)))
    rgb = hsv_to_rgb(hsv[0], hsv[1], hsv[2])
    return tuple(int(x) for x in rgb)


def draw_tag_bubbles(img, tags, fill, text_color, font):
    start = 60
    high_point = DESIRED_H - 95
    low_point = high_point + 80

    if not tags:
        return

    draw = ImageDraw.Draw(img)

    if len(tags) > 3:
        add = len(tags) - 3
        tags = tags[:3] + [f"+{add}"]

    for tag in tags:
        text_width, _ = font.getsize(tag)
        x1 = start
        x2 = x1 + text_width + 70  # higher hard-coded value -> wider tags
        y1 = high_point
        y2 = low_point

        draw.rounded_rectangle((x1, high_point, x2, low_point), fill=fill,
                                width=2, radius=45)
        draw_bubble_text(img, tag, ((x1+x2)/2, (y1+y2)/2),
                  text_color, FONT_TAGS, 2, fill)
        start = start + text_width + 90  # higher value -> tags further apart


def blur_img(img):
    temp = img.copy()
    temp = temp.filter(ImageFilter.GaussianBlur(3))
    img.paste(temp)


def darken_img(img):
    temp = img.copy()
    enhancer = ImageEnhance.Brightness(temp)

    # reduce brightness (e.g. 0.20 reduces it to 20%)
    temp = enhancer.enhance(0.85)
    img.paste(temp)


def draw_bubble_text(img, text, position, fill, font, stroke_width,
                     stroke_fill):
    draw = ImageDraw.Draw(img)

    draw.text(position, text, fill=fill, font=font, stroke_width=stroke_width,
              stroke_fill=stroke_fill, anchor='mm')


def draw_title_text(img, text, y, min_x, max_x, fill):
    font = FONT_TITLE
    draw = ImageDraw.Draw(img)
    size = font.getsize(text)
    max_width = max_x - min_x

    edited = False

    size = font.getsize(text)
    while size[0] > max_width:
        edited = True
        text = text[:-1]
        size = font.getsize(text)

    if edited:
        text = text[:-3] + "..." if text[-4] == ' ' else text[:-3] + " ..."
        size = font.getsize(text)

    draw.text((max_x-size[0], y), text, fill=fill, font=font)


def crop_img(img):
    width, height = img.size

    if width==height:
        return img
    offset = abs(width-height)//2

    if width>height:
        left = offset
        top = 0
        right = width - offset
        bottom = height
    else:
        left = 0
        top = offset
        right = width
        bottom = height - offset

    return img.crop((left, top, right, bottom))


async def setup(bot: commands.Bot):
    await bot.add_cog(Events(bot))