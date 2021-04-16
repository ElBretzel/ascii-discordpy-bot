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
    new_height = int(new_width * ratio) or 1
    return image.resize((new_width, new_height), Image.ANTIALIAS)


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


def write_ascii(drawable_image, ctx, ascii_image, hextype):
    for n, art in enumerate(ascii_image):
        drawable_image.text((0, n * (FONT_SIZE + 3)), art, font=font, fill=hextype)


def extract_args(args):
    if not args:
        return {}
    return {i: j for i, j in [i.split("=") for i in args if len(i.split("=")) > 1] if
            i in ["bg", "color", "speed", "reverse"]}


async def send_image(ctx, images, loop, executor):
    # https://stackoverflow.com/questions/58664698/error-decode-byte-when-send-image-in-discord
    with BytesIO() as image_binary:
        await loop.run_in_executor(executor, lambda: images[0].save(fp=image_binary, format='GIF', append_images=images[1:],
                                                                save_all=True, loop=0, optimize=0, quality=10))

        image_binary.seek(0)

        await ctx.send(file=discord.File(fp=image_binary, filename="asciify.gif"))


def check_hexcolor(hexcode):
    if not hexcode.get("color") and not hexcode.get("bg"):
        return [(255, 255, 255, 255), (54, 57, 63)]
    elif not hexcode.get("color"):
        return [(255, 255, 255, 255), convert_hex_rgb(hexcode.get("bg"))]
    elif not hexcode.get("bg"):
        return [convert_hex_rgb(hexcode.get("color")), (54, 57, 63)]
    return [convert_hex_rgb(hexcode.get("color")), convert_hex_rgb(hexcode.get("bg"))]


class GenAscii(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.command()
    async def genascii(self, ctx, *args):
        """
        args can be:
        
        bg : str
            hexcode        
        color : str
            hexcode
        speed : int
            multiply the speed of the gif
        reverse: bool
            reverse the grayscale
        """
        if not ctx.message.attachments:
            await ctx.message.delete()
            return

        image = await read_attachment(ctx)
        await ctx.message.delete()

        args = extract_args(args)
        ascii_chars = correct_ascii_display(niveau[15 - 1], args)
        loop = asyncio.get_running_loop()
        executor = ThreadPoolExecutor()
        hexcode = check_hexcolor(args)

        if image.mode == "RGBA":
            image = await loop.run_in_executor(executor, lambda: replace_transparancy(image))

        gen = int(72 // float(args.get("speed", 1)))
        message = await ctx.send(f"Progress 0/{gen} frames")
        imgs = []

        for i in range(gen, 0, -1):
            if i % 8 == 0 or i == 1:
                await message.edit(content=f"Progress: {abs(i - gen)}/{gen} frames")

            # Conversion de l'image (180px max)
            new_width = image.width if image.width <= int(i * float(args.get("speed", 1))) else int(
                i * float(args.get("speed", 1)))
            new_size = await loop.run_in_executor(executor, lambda: resize_image(image, new_width))

            # Transformation de chaque pixel de l'image en asciiart
            new_image_data = await loop.run_in_executor(executor,
                                                        lambda: pixels_to_ascii(grayify(new_size), ascii_chars))

            # création d'une liste contenant plusieurs listes qui vont représenter une ligne de l'image
            ascii_image = [new_image_data[index:(index + new_width)] for index in
                           range(0, len(new_image_data), new_width)]

            # variables
            cols = len(ascii_image)
            width, height = new_size.size

            # Création d'une nouvelle image vierge
            width_ascii = width * WIDTH_SIZE  # EACH CHAR HAVE 6PX OF WIDTH
            height_ascii = cols * (FONT_SIZE + 3)  # EACH CHAR HAVE 13PX OF HEIGHT
            text_image = Image.new('RGBA', (width_ascii, height_ascii), hexcode[1])

            # création d'une image pouvant être écrite
            drawable_image = ImageDraw.Draw(text_image)

            # Ecriture sur l'image (prends du temps)
            await loop.run_in_executor(executor, lambda: write_ascii(drawable_image, ctx, ascii_image, hexcode[0]))

            # Redimention pour que ca ressemble a l'image de base
            if i == gen:
                resize_width = int((round((width * (height_ascii // 2)) / height, 0)))
                resize_heigh = int(height_ascii // 2)

            imgs.append(text_image.resize((resize_width, resize_heigh)))

        imgs = imgs[::-1]
        imgs.extend([imgs[-1]] * 5)

        await message.delete()
        await send_image(ctx, imgs, loop, executor)
        
def setup(client):
    client.add_cog(GenAscii(client))
