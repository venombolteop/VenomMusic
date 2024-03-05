import asyncio
import os
import random
import re
import textwrap
import aiofiles
import aiohttp
from PIL import (Image, ImageDraw, ImageEnhance, ImageFilter,
                 ImageFont, ImageOps)
from youtubesearchpython.__future__ import VideosSearch
import numpy as np
from config import YOUTUBE_IMG_URL


def make_col():
    return (random.randint(0,255),random.randint(0,255),random.randint(0,255))


def changeImageSize(maxWidth, maxHeight, image):
    widthRatio = maxWidth / image.size[0]
    heightRatio = maxHeight / image.size[1]
    newWidth = int(widthRatio * image.size[0])
    newHeight = int(heightRatio * image.size[1])
    newImage = image.resize((newWidth, newHeight))
    return newImage

def truncate(text):
    list = text.split(" ")
    text1 = ""
    text2 = ""    
    for i in list:
        if len(text1) + len(i) < 30:        
            text1 += " " + i
        elif len(text2) + len(i) < 30:       
            text2 += " " + i

    text1 = text1.strip()
    text2 = text2.strip()     
    return [text1,text2]

async def get_thumb(videoid):
    try:
        if os.path.isfile(f"cache/{videoid}.jpg"):
            return f"cache/{videoid}.jpg"

        url = f"https://lh3.googleusercontent.com/pw/AP1GczPYxt7ufkF6pTEnJUFw4RlN_CTplkoR6rxnEkwT4btBbb2aS4vowH23y4qqA7t2yCT11Ni46zfnE5r7Zz4BqCMTVqphXKKB2oDy-Q_JUw23_BGo1r1ABY_QlA13TafP6Qcg7i7By15qtTZCZ3kRdCE=w720-h1280-s-no-gm?authuser=0}"
        if 1==1:
            img_arr,lum_img_arr))
            image3 = Image.fromarray(final_img_arr)
            image3 = image3.resize((600,600))
            

            image2.paste(image3, (50,70), mask = image3)
            image2.paste(circle, (0,0), mask = circle)

            # fonts
            font1 = ImageFont.truetype('VenomX/assets/font.ttf', 30)
            font2 = ImageFont.truetype('VenomX/assets/font2.ttf', 70)
            font3 = ImageFont.truetype('VenomX/assets/font2.ttf', 40)
            font4 = ImageFont.truetype('VenomX/assets/font2.ttf', 35)

            
