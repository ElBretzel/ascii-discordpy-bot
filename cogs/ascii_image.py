import time
import math
import asyncio
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor

import discord
from discord.ext import commands
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from PIL import ImageColor

ASCII_CHARS = "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\|()1{}[]?-_+~<>i!lI;:,\"^`' "
niveau = [2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 14, 18, 23, 35, 69]
FONT_SIZE = 10
WIDTH_SIZE = 6
font = ImageFont.truetype("cour.ttf", FONT_SIZE)


# Redimension de l'image
def resize_image(image, new_width):
    width, height = image.size
    ratio = height / width
    new_height = int(new_width * ratio)
    return image.resize((new_width, new_height))


# Convertit tout les pixels en gris
def grayify(image):
    return image.convert("L")


# Convers tout les pixels en ASCII
def pixels_to_ascii(image, ascii_chars):
    # Recupere l'information de couleur de tout les pixels
    pixels = image.getdata()
    # On recupere le caractères dans le string de tout les ascii par rapport a l'information de la couleur
    # divise la l'intensité de la couleur du pixel par le nombre de couleur total divisé par la longueur du string ascii
    # on arrondis et transforme en nombre entier pour transformer en un indice pour récupere l'ascii adapté
    a = [int(i // math.floor(255 / len(ascii_chars))) for i in pixels]
    a = [len(ascii_chars) - 1 if i >= len(ascii_chars) else i for i in a]
    return "".join(ascii_chars[pixel] for pixel in a)


async def read_attachment(ctx):
    image = ctx.message.attachments[0]
    image = await image.to_file()
    image = Image.open(image.fp)
    return image


def level_correction(level):
    if not level.isdigit():
        return 15
    if int(level) > 15:
        return 15
    if int(level) <= 0:
        return 1
    return int(level)


def correct_ascii_display(precision, args):
    ascii_chars = [i for i in ASCII_CHARS]
    reverse = -1 if args.get("reverse", 0) == "1" else 1
    ascii_chars = ascii_chars[::reverse]
    return ascii_chars[::math.ceil(len(ascii_chars) / precision)]


def replace_transparancy(image):
    new_image = Image.new("RGBA", image.size, "WHITE")
    new_image.paste(image, (0, 0), image)
    return new_image.convert('RGB')


def convert_hex_rgb(hexcode):
    return ImageColor.getrgb(hexcode)


async def write_ascii(drawable_image, ctx, ascii_image, hextype, executor, loop):
    t1 = time.time()
    completion = 0

    for n, art in enumerate(ascii_image):
        await loop.run_in_executor(executor,
                                   lambda: drawable_image.text((0, n * (FONT_SIZE + 3)), art, font=font, fill=hextype))
        if int((n / len(ascii_image)) * 100) == 10 * completion:
            if completion == 1:
                t2 = time.time()
                temps = round((t2 - t1) * 10, 2)
                await ctx.send(f"Estimated time: {temps} seconds", delete_after=temps)
            completion += 1


def extract_args(args):
    if not args:
        return {}
    return {i: j for i, j in [i.split("=") for i in args if len(i.split("=")) > 1] if
            i in ["bg", "color", "width", "reverse", "level"]}


def image_correction(txt, width, height, height_ascii):
    resize_width = int(round((width * height_ascii) / height, 0))
    return txt.resize((resize_width, height_ascii))


async def send_image(ctx, image):
    # https://stackoverflow.com/questions/58664698/error-decode-byte-when-send-image-in-discord
    with BytesIO() as image_binary:
        image.save(image_binary, "PNG")
        image_binary.seek(0)
        await ctx.send(file=discord.File(fp=image_binary, filename="asciify.png"))


def check_hexcolor(hexcode):
    if not hexcode.get("color") and not hexcode.get("bg"):
        return [(255, 255, 255, 255), (54, 57, 63)]
    elif not hexcode.get("color"):
        return [(255, 255, 255, 255), convert_hex_rgb(hexcode.get("bg"))]
    elif not hexcode.get("bg"):
        return [convert_hex_rgb(hexcode.get("color")), (54, 57, 63)]
    return [convert_hex_rgb(hexcode.get("color")), convert_hex_rgb(hexcode.get("bg"))]


class Asciimage(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.command()
    async def asciify(self, ctx, *args):
        """
        args can be:
        
        bg : str
            hexcode        
        color : str
            hexcode
        wdth : int
            width of the final output
        reverse: bool
            reverse the grayscale
        level: int
            level of asciify (1 - 15)
        """
        
        if not ctx.message.attachments:
            await ctx.message.delete()
            return

        image = await read_attachment(ctx)
        args = extract_args(args)
        level = level_correction(args.get("level", "15"))
        await ctx.message.delete()

        # On recupere un string de l'ascii par rapport a la précision demandé

        ascii_chars = correct_ascii_display(niveau[level - 1], args)
        loop = asyncio.get_running_loop()
        executor = ThreadPoolExecutor()

        # Remplace la transparance par du blanc
        if image.mode == "RGBA":
            image = await loop.run_in_executor(executor, lambda: replace_transparancy(image))

        width = int(args.get("width", 128)) if args.get("width") else 128
        width = min(width, 256)
        # Conversion de l'image (180px max)
        new_width = image.width if image.width <= width else width
        new_size = await loop.run_in_executor(executor, lambda: resize_image(image, new_width))

        # Transformation de chaque pixel de l'image en asciiart
        new_image_data = await loop.run_in_executor(executor, lambda: pixels_to_ascii(grayify(new_size), ascii_chars))

        # création d'une liste contenant plusieurs listes qui vont représenter une ligne de l'image
        ascii_image = [new_image_data[index:(index + new_width)] for index in range(0, len(new_image_data), new_width)]

        # variables
        cols = len(ascii_image)
        width, height = new_size.size
        hexcode = check_hexcolor(args)

        # Création d'une nouvelle image vierge
        width_ascii = width * WIDTH_SIZE  # EACH CHAR HAVE 6PX OF WIDTH
        height_ascii = cols * (FONT_SIZE + 3)  # EACH CHAR HAVE 13PX OF HEIGHT
        text_image = Image.new('RGBA', (width_ascii, height_ascii), hexcode[1])

        # création d'une image pouvant être écrite
        drawable_image = ImageDraw.Draw(text_image)

        # Ecriture sur l'image (prends du temps)
        await write_ascii(drawable_image, ctx, ascii_image, hexcode[0], executor, loop)

        # Redimention pour que ca ressemble a l'image de base
        text_image = image_correction(text_image, width, height, height_ascii)

        # sauvegarde de l'image

        await send_image(ctx, text_image)

def setup(client):
    client.add_cog(Asciimage(client))
