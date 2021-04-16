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
from PIL import ImageSequence

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
    if image.is_animated:
        return image
    return


def correct_ascii_display(precision, args):
    ascii_chars = [i for i in ASCII_CHARS]
    reverse = -1 if args.get("reverse", 0) == "1" else 1
    ascii_chars = ascii_chars[::reverse]
    return ascii_chars[::math.ceil(len(ascii_chars) / precision)]


def convert_hex_rgb(hexcode):
    return ImageColor.getrgb(hexcode)


def write_ascii(drawable_image, ctx, ascii_image, hextype):
    for n, art in enumerate(ascii_image):
        drawable_image.text((0, n * (FONT_SIZE + 3)), art, font=font, fill=hextype)


def extract_args(args):
    if not args:
        return {}
    return {i: j for i, j in [i.split("=") for i in args if len(i.split("=")) > 1] if
            i in ["bg", "color", "reverse", "speed"]}


async def send_image(ctx, images, loop, duration, executor):
    # https://stackoverflow.com/questions/58664698/error-decode-byte-when-send-image-in-discord
    with BytesIO() as image_binary:
        await loop.run_in_executor(executor, lambda: images[0].save(fp=image_binary, format='GIF', append_images=images[1:],
                                                                save_all=True, loop=0, optimize=0, quality=10, duration=duration))
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


def convert_frame_image(frames, skip_frames):
    for i, frame in enumerate(frames):
        if i + 1 % skip_frames != 0:
            thumbnail = frame.copy()
            yield thumbnail


def reduce_frame(image, max_frames):
    return 1 + sum(i % max_frames == 0 for i in range(1, image.n_frames + 1))


def image_correction(txt, width, height, height_ascii):
    resize_width = int(round((width * height_ascii) / height, 0))
    return txt.resize((resize_width, height_ascii))


def replace_transparancy(image):
    new_image = Image.new("RGBA", image.size, "WHITE")
    new_image.paste(image, (0, 0), image)
    return new_image.convert('RGB')


class Gascii(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.command()
    async def gascii(self, ctx, *args):
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

        if not image:
            return

        duration = image.info['duration']
        frames = ImageSequence.Iterator(image)
        args = extract_args(args)
        ascii_chars = correct_ascii_display(niveau[15 - 1], args)
        loop = asyncio.get_running_loop()
        executor = ThreadPoolExecutor()
        hexcode = check_hexcolor(args)
        max_frames = min(int(64 / float(args.get("speed", 1))), image.n_frames)
        skip_frames = await loop.run_in_executor(executor, lambda: reduce_frame(image, max_frames))
        imgs = []

        message = await ctx.send(f"Progress 0/{max_frames} frames")
        frames = convert_frame_image(frames, skip_frames)

        for i in range(max_frames):

            if i == image.n_frames:
                break

            if i % 4 == 0 or i == 0:
                await message.edit(content=f"Progress: {i}/{max_frames} frames")

            # Conversion de l'image (64px max)
            frame = next(frames)

            # Remplace la transparance par du blanc
            if frame.mode == "RGBA":
                frame = await loop.run_in_executor(executor, lambda: replace_transparancy(frame))

            new_width = frame.width if frame.width <= 64 else 64
            new_size = await loop.run_in_executor(executor, lambda: resize_image(frame, new_width))

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
            imgs.append(image_correction(text_image, width, height, height_ascii // 2))

        await message.delete()
        await send_image(ctx, imgs, loop, duration, executor)
        
def setup(client):
    client.add_cog(Gascii(client))
