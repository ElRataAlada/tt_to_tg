import os
import re
from aiogram.utils.markdown import hlink

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters, Application, CallbackQueryHandler
from datetime import datetime, timedelta
from functools import partial
from videoprops import get_video_properties

import asyncio
from concurrent.futures import ThreadPoolExecutor
import requests
from hurry.filesize import size
from parsel import Selector
import argparse
import shutil
import os
import time
import re
import json
import io
import PIL.Image as Image
from moviepy.editor import AudioFileClip, VideoFileClip, concatenate_videoclips, concatenate_audioclips

from pytubefix import YouTube

TT_TO_TG_USERS = ["@n2y2k2", "@Naykonnn", "@Colt1911M1", "@unknown1233734554", "@alismme", "@ihatemyselfbutyoumore", "@idinicka", "@duffeydd"]


class Colors:
    def red(text):
        return f"\033[91m{text}\033[0m"

    def green(text):
        return f"\033[92m{text}\033[0m"

    def yellow(text):
        return f"\033[93m{text}\033[0m"

    def blue(text):
        return f"\033[94m{text}\033[0m"

parser = argparse.ArgumentParser(description="Multitok: A simple script that downloads TikTok videos concurrently.")
watermark_group = parser.add_mutually_exclusive_group()
parser.add_argument("--links", default="links.txt", help="The path to the .txt file that contains the TikTok links. (Default: links.txt)")
watermark_group.add_argument("--no-watermark", action="store_true", help="Download videos without watermarks. (Default)")
watermark_group.add_argument("--watermark", action="store_true", help="Download videos with watermarks.")
parser.add_argument("--workers", default=3, help="Number of concurrent downloads. (Default: 3)", type=int)
parser.add_argument("--api-version", choices=['v1', 'v2'], default='v2', help="API version to use for downloading videos. (Default: v2)")
parser.add_argument("--save-metadata", action="store_true", help="Write video metadata to file if specified.")
args = parser.parse_args()

headers = {
'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}

def extract_video_id(url):
    response = requests.get(url, headers=headers)
    url = response.url
    
    content_type_pattern = r"/(video|photo)/(\d+)"

    content_type_match = re.search(content_type_pattern, url)
    content_type = content_type_match.group(1)
    video_id = content_type_match.group(2)

    return content_type, video_id

def split(arr, size):
     arrs = []
     while len(arr) > size:
         pice = arr[:size]
         arrs.append(pice)
         arr   = arr[size:]
     arrs.append(arr)
     return arrs
   
executor = ThreadPoolExecutor()
   
async def download_v1(link):
    time_start = time.time()

    headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:107.0) Gecko/20100101 Firefox/107.4',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Origin': 'https://tmate.cc',
    'Connection': 'keep-alive',
    'Referer': 'https://tmate.cc/',
    'Sec-Fetch-Site': 'same-origin',
    }
    try:

        content_type, vide_id = extract_video_id(link)

        file_name = "videos/" + vide_id

        with requests.Session() as s:
            response = s.get("https://tmate.cc/", headers=headers)

            selector = Selector(response.text)
            token = selector.css('input[name="token"]::attr(value)').get()
            data = {'url': link, 'token': token}

            response = s.post('https://tmate.cc/action', headers=headers, data=data).json()["data"]

            selector = Selector(text=response)

            if content_type == "video":
              download_link_index = 3 if args.watermark else 0
              download_link = selector.css('.downtmate-right.is-desktop-only.right a::attr(href)').getall()[download_link_index]

              response = s.get(download_link, headers=headers)

              video = io.BytesIO(response.content)
              video.name = 'video.mp4'

              time_end = time.time()
              print(f"{Colors.blue(link)} downloaded {Colors.green('successfully')}. Time: {Colors.yellow(round((time_end - time_start), 2))} {Colors.yellow('s')}")

              return video
            else:
                base_size = 500

                if not os.path.exists(f"{file_name}"):
                    os.mkdir(f"{file_name}")
                    os.mkdir(f"{file_name}/photos/")
                else:
                    shutil.rmtree(f"{file_name}")
                    os.mkdir(f"{file_name}")
                    os.mkdir(f"{file_name}/photos/")

                # Audio
                audio_link = selector.xpath('/html/body/div/div/div[2]/div/a/@href').get()

                response = s.get(audio_link, headers=headers)

                with open(f"{file_name}/audio.mp3", 'wb') as file:
                    file.write(response.content)

                audio = AudioFileClip(f"{file_name}/audio.mp3")

                # Photos
                download_links = selector.css('.card-img-top::attr(src)').getall()
                photos = []

                max_size = (0, 0)

                for index, download_link in enumerate(download_links):
                    response = s.get(download_link, headers=headers)
                    image = Image.open(io.BytesIO(response.content)).convert("RGB")
                    photos.append(image)

                    if image.size[0] > max_size[0]:
                        max_size = image.size

                clips = []

                for index, img in enumerate(photos):
                    wpercent = (base_size / float(img.size[0]))
                    hsize = int((float(img.size[1]) * float(wpercent)))
                    img = img.resize((base_size, hsize), Image.Resampling.LANCZOS)
                    img.save(f"{file_name}/photos/{index}.jpeg")
                
                # Video
                for name in os.listdir(f"{file_name}/photos"):
                    clip = VideoFileClip(f"{file_name}/photos/{name}").set_duration(4)

                    transition_duration = 0.3
                    duration = clip.duration

                    if len(clips) > 0:
                        clip1 = clip.subclip(0, transition_duration)
                        clip2 = clip.subclip(transition_duration, duration - transition_duration)
                        clip3 = clip.subclip(duration-transition_duration, duration)

                        clip1 = clip1.crossfadein(transition_duration)
                        clip3 = clip3.crossfadeout(transition_duration)
                        clip = concatenate_videoclips([clip1, clip2, clip3], method="compose")
                    else:
                        duration = duration - 1
                        clip.set_duration(duration)
                        clip1 = clip.subclip(0, duration-transition_duration)
                        clip3 = clip.subclip(duration-transition_duration, duration)

                        clip3 = clip1.crossfadeout(transition_duration)
                        clip = concatenate_videoclips([clip1, clip3], method="compose")

                    clips.append(clip)
                    # clips.append(VideoFileClip(f"{file_name}/photos/{name}").set_duration(duration / len(photos)))
                
                video = concatenate_videoclips(clips, method="compose")

                while audio.duration < video.duration:
                    audio = concatenate_audioclips([audio, audio])

                audio = audio.subclip(0, video.duration)

                clip = video.set_audio(audio)
                clip.write_videofile(f"{file_name}/video.mp4", fps=30,audio=True)

                with open(f"{file_name}/video.mp4", 'rb') as file:
                    video = file.read()

                audio.close()

                shutil.rmtree(f"{file_name}")
                    
                video = io.BytesIO(video)
                video.name = 'video.mp4'

                time_end = time.time()
                print(f"{Colors.blue(link)} downloaded {Colors.green('successfully')}. Time: {Colors.yellow(round((time_end - time_start), 2))} {Colors.yellow('s')}")

                return video

    except Exception as e:
        print(f"{Colors.blue(link)}")
        print(f"{Colors.red('Error')}: {e}")

        with open("errors.txt", 'a') as error_file:
            error_file.write(link + "\t" + str(e) + "\n")




# def download_v2(link):
#     headers = {
#     'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0',
#     'Sec-Fetch-Site': 'same-origin',
#     'Content-Type': 'application/x-www-form-urlencoded',
#     'Origin': 'https://musicaldown.com',
#     'Connection': 'keep-alive',
#     'Referer': 'https://musicaldown.com/en?ref=more',
#     }


#     _, file_name, content_type = extract_video_id(link)

#     with requests.Session() as s:
#         try:
#             file_name = None
#             r = s.get("https://musicaldown.com/en", headers=headers)

#             selector = Selector(text=r.text)

#             token_a = selector.xpath('//*[@id="link_url"]/@name').get()
#             token_b = selector.xpath('//*[@id="submit-form"]/div/div[1]/input[2]/@name').get()
#             token_b_value = selector.xpath('//*[@id="submit-form"]/div/div[1]/input[2]/@value').get()

#             data = {
#                 token_a: link,
#                 token_b: token_b_value,
#                 'verify': '1',
#             }

#             response = s.post('https://musicaldown.com/en', headers=headers, data=data)
#             selector = Selector(text=response.text)

#             if content_type == "video":
#                 watermark = selector.xpath('/html/body/div[2]/div/div[2]/div[2]/a[4]/@href').get()
#                 no_watermark = selector.xpath('/html/body/div[2]/div/div[2]/div[2]/a[1]/@href').get()

#                 print(watermark, no_watermark)

#                 download_link = watermark if args.watermark else no_watermark

#                 response = s.get(download_link, stream=True, headers=headers)

#                 folder_name = downloader(file_name, link, response, extension="mp4")
#             else:
#                 download_links = selector.xpath('//div[@class="card-image"]/img/@src').getall()

#                 for index, download_link in enumerate(download_links):
#                     response = s.get(download_link, stream=True, headers=headers)
#                     folder_name = downloader(f"{file_name}_{index}", link, response, extension="jpeg")

#             return folder_name, content_type

#         except Exception as e:
#             print(f"\033[91merror\033[0m: {link} - {str(e)}")
#             with open("errors.txt", 'a') as error_file:
#                 error_file.write(link + "\n")





async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Отправь ссылку на видео с tiktok и получи видео")

async def id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Твой id: `{update.effective_user.id}`\nID чата: `{update.effective_chat.id}`", parse_mode="MarkdownV2")

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender_name = update.effective_user.username

    chat_id = update.effective_chat.id

    if os.path.exists(f"admins_{chat_id}.txt") == False:
        open(f"admins_{chat_id}.txt", "w+").write("Hohol_tt_bot\ncriceta0").close()

    admins = open(f"admins_{chat_id}.txt", "r+").readlines()

    message_text = update.message.text

    message_text = message_text.replace("@Hohol_tt_bot", "")
    
    # /ban_tt @username N

    to_ban_user = message_text.split(" ")[1].replace("@", "")
    ban_time = 0

    if len(message_text.split(" ")) == 2:
        ban_time = "None"
    else:
        ban_time = message_text.split(" ")[2]


    if sender_name not in admins and to_ban_user in admins:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Забанить админа? А ты наглый, держи бан на 2 часа 😁", reply_to_message_id=update.message.message_id, disable_notification=True)
        ban_user(chat_id, sender_name, 5)
        return
    
    elif sender_name not in admins or to_ban_user == "Hohol_tt_bot":
        await context.bot.send_message(chat_id=update.effective_chat.id, text="У тебя нет прав, успокойся", reply_to_message_id=update.message.message_id, disable_notification=True)
        return
    
    elif to_ban_user not in admins:        
        total_ban = ban_user(chat_id, to_ban_user, ban_time)
        
        if ban_time == "None":
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Пользователь забанен навсегда", reply_to_message_id=update.message.message_id, disable_notification=True)
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Пользователь забанен на {total_ban} часов", reply_to_message_id=update.message.message_id, disable_notification=True)
        return

async def tt_ban_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if os.path.exists(f"banned_{chat_id}.txt") == False:
        open(f"banned_{chat_id}.txt", "w+").close()

    with open(f"banned_{chat_id}.txt", "r+") as file:
        lines = file.readlines()

        if len(lines) == 0:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Список забаненных пуст", disable_notification=True)
            return

        message = "Список забаненных:\n"

        for line in lines:
            banned_username, banned_time, ban_time = line.split(" ")

            if ban_time == "None":
                message += f"@{banned_username} - навсегда\n"
            else:
                message += f"@{banned_username} - { round(((datetime.fromtimestamp(banned_time) + timedelta(hours=ban_time) - datetime.now()).total_seconds() / 60), 0) } ч\n"

        await context.bot.send_message(chat_id=update.effective_chat.id, text=message, disable_notification=True)

def ban_user(chat_id, username, time):
    if os.path.exists(f"banned_{chat_id}.txt") == False:
        open(f"banned_{chat_id}.txt", "w+").close()

    lines = open(f"banned_{chat_id}.txt", "r+").readlines()

    found = False
    total_ban = time

    with open(f"banned_{chat_id}.txt", "w+") as file:
        for line in lines:
            banned_username, banned_time, ban_time = line.split(" ")

            if banned_username == username:
                found = True
                if time == "None":
                    ban_time = "None"
                else:
                    ban_time = str(int(ban_time) + int(time))
                    total_ban = int(ban_time)
                
                lines.remove(line)
                lines.append(f"{username} {datetime.now().timestamp()} {ban_time}\n")
                break

        if not found:
            lines.append(f"{username} {datetime.now().timestamp()} {time}\n")
            
        file.writelines(lines)

    return total_ban

def is_banned(chat_id, username):
    if os.path.exists(f"banned_{chat_id}.txt") == False:
        open(f"banned_{chat_id}.txt", "w+").close()

    with open(f"banned_{chat_id}.txt", "r+") as file:
        lines = file.readlines()

        for line in lines:
            banned_username, banned_time, ban_time = line.split(" ")

            if ban_time == "None":
                return True, None

            banned_time = float(banned_time)
            ban_time = int(ban_time)

            if banned_username == username:
                if datetime.fromtimestamp(banned_time) + timedelta(hours=ban_time) <= datetime.now():
                    unban_user(chat_id, username)
                    return False, 0
                else:
                    return True, round(((datetime.fromtimestamp(banned_time) + timedelta(hours=ban_time) - datetime.now()).total_seconds() / 60), 0)

    return False, 0

def unban_user(chat_id, username):
    with open(f"banned_{chat_id}.txt", "r") as file:
        lines = file.readlines()

    was_banned = False

    with open(f"banned_{chat_id}.txt", "w") as file:
        for line in lines:
            banned_username, banned_time, ban_time = line.split(" ")

            if banned_username == username:
                was_banned = True

            if banned_username != username:
                file.write(line)

    return was_banned

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender_name = update.effective_user.username

    chat_id = update.effective_chat.id

    if os.path.exists(f"admins_{chat_id}.txt") == False:
        open(f"admins_{chat_id}.txt", "w+").write("Hohol_tt_bot\ncriceta0").close()

    admins = open(f"admins_{chat_id}.txt", "r+").readlines()

    message_text = update.message.text

    message_text = message_text.replace("@Hohol_tt_bot", "")
    
    # /ban_tt @username N

    to_ban_user = message_text.split(" ")[1].replace("@", "")

    if sender_name not in admins:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="У тебя нет прав, успокойся", reply_to_message_id=update.message.message_id, disable_notification=True)
        return
    
    elif to_ban_user not in admins:        
        was_banned = unban_user(chat_id, to_ban_user)

        if was_banned:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Пользователь разбанен", reply_to_message_id=update.message.message_id, disable_notification=True)
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Пользователь не был забанен", reply_to_message_id=update.message.message_id, disable_notification=True)
        
        return
def create_progress_bar(progress, total, width=30):
    progress_ratio = progress / total
    filled_length = int(width * progress_ratio)
    bar = "█" * filled_length + "-" * (width - filled_length)
    percentage = int(progress_ratio * 100)
    return f"[{bar}] {percentage}%"

async def handle_quality_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
        await query.delete_message()
        return

    message_id, quality, text = query.data.split(":")
    url = f"https://youtube.com/{text}"

    link = hlink("🔗 Ссылка", url)

    await context.bot.delete_message(chat_id=query.message.chat_id, message_id=message_id)
    await query.delete_message()

    new_message = await context.bot.send_message(
        update.effective_chat.id,
        text=f"{link} {quality}",
        parse_mode="HTML",
        disable_web_page_preview=True,
    )

    # Use the wrapper for the on_progress callback
    yt = YouTube(
        url,
        allow_oauth_cache=True,
        use_oauth=False,
        on_progress_callback=on_progress_wrapper(
            chat_id=new_message.chat_id,
            message_id=new_message.message_id,
            context=context,
        ),
    )

    # Filter streams
    streams = yt.streams.filter(type="video", file_extension="mp4", resolution=quality).order_by("resolution")
    
    progressive_streams = streams.filter(progressive=True)

    stream = None
    progressive = False

    if len(progressive_streams) > 0:
      stream = progressive_streams.first()
      progressive = True 
       
    else :
      stream = streams.first()
      progressive = False

    filesize = size(stream.filesize)
    title = stream.title

    # Download video
    file_path = stream.download("videos")

    if not progressive:
        audio = yt.streams.filter(type="audio").order_by("abr").last()

        audio_file_path = audio.download("videos")

        context.bot.edit_message_text(
            chat_id=new_message.chat_id,
            message_id=new_message.message_id,
            text=f"{title}\n\nОбрабатываю видео, это занимает примерно 15мин на час видео :(\n{link} {quality} ({filesize})",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        
        video = VideoFileClip(file_path)
        audio = AudioFileClip(audio_file_path)

        video = video.set_audio(audio)
        
        video.write_videofile(file_path, codec="libx264", audio_codec="aac", fps=stream.fps, threads=12)
        
        audio.close()
        
        os.remove(audio_file_path)


    # Send video
    await new_message.edit_text(
        f"{title}\n\nОтправляю видео...\n{link} {quality} ({filesize})",
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    
    props = get_video_properties(file_path)

    await context.bot.send_video(
        chat_id=update.effective_chat.id,
        video=file_path,
        supports_streaming=True,
        caption=f"{title}\n\n{link}",
        parse_mode="HTML",
        width=props["width"],
        height=props["height"],
        write_timeout=1000,
        read_timeout=1000,
        pool_timeout=1000,
        connect_timeout=1000,
    )

    await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=new_message.message_id)
    
    os.remove(file_path)

def on_progress_wrapper(chat_id, message_id, context):
    def on_progress(stream, chunk, bytes_remaining):
        total_size = stream.filesize
        bytes_downloaded = total_size - bytes_remaining

        downloaded = size(bytes_downloaded)
        filesize = size(total_size)

        progress_text = (
            f"{stream.title}\n\n"
            f"{create_progress_bar(bytes_downloaded, total_size)}\n"
            f"{stream.url} {stream.resolution} ({downloaded}/{filesize})"
        )

        context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=progress_text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

    return on_progress


async def send_text_inner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    sender_username = message.from_user.username
    chat_id = update.effective_chat.id
    
    if chat_id == 7344659725 and message.text.split(" ")[0] == "@to":
        text = message.text.split(" ")[1:]
        
        await context.bot.send_message(chat_id="-1002005871510", text=" ".join(text))
                    
        return

    elif re.compile('https://[a-zA-Z]+.tiktok.com/').match(message.text):
        print(f"Received: {message.text}")
        index = message.text.find("tiktok.com/") + 9 + len("tiktok.com/") 
        tt_link = message.text[0:index]
        subtext = message.text[index+1:].strip()
        
        banned, ban_time = is_banned(chat_id, sender_username)

        if banned:
            await context.bot.delete_message(chat_id, message.message_id)
            
            if ban_time == None:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Ты забанен навсегда! Не расстраюйся", disable_notification=True)
            else:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Ты забанен! Еще {round(ban_time / 60, 1)} ч", disable_notification=True)
            
            return

        try:
            sender_username = message.from_user.username
            bot = context.bot

            chat_id = update.effective_chat.id

            chat_type = update.effective_chat.type

            link = hlink('🔗 Ссылка', tt_link)

            caption = f'👤 @{sender_username}\n{link}'
            
            if len(subtext) != 0:
              caption = f'💬: {subtext}\n\n👤 @{sender_username}\n{link}'
    
            video = await download_v1(tt_link)

            if chat_type == 'group' or chat_type == 'supergroup':
                await bot.sendVideo(chat_id, video, supports_streaming=True, disable_notification=True, caption=caption, parse_mode='HTML')
                await bot.deleteMessage(chat_id, message.message_id)

            elif chat_type == 'private':
                await bot.sendVideo(chat_id, video, supports_streaming=True, disable_notification=True, reply_to_message_id=message.message_id)

        except Exception as e:
            print(f"{Colors.red('Error')}: {e}")



async def send_text(update: Update, context: ContextTypes.DEFAULT_TYPE):   
    await asyncio.create_task(send_text_inner(update, context))

token = '7295842483:AAEQ5-zt-0HeB3gy52NYDYuJ7Db6Ub4W1-0'
base_url = 'http://127.0.0.1:1337/bot'

from telethon import TelegramClient, events

import json
import requests
import multiprocessing

APP_ID = 11752929
APP_HASH = "d20a3d3e25c7119e061cf3ef1e02bf5b"
PHONE_NUMBER = "+380681076854"

HOHOL_CHAT_ID = 7295842483
TOKEN = "7295842483:AAEQ5-zt-0HeB3gy52NYDYuJ7Db6Ub4W1-0"

client = TelegramClient('@criceta0', APP_ID, APP_HASH)


@client.on(events.NewMessage(chats = [HOHOL_CHAT_ID]))
async def debtors(event):
    message = event.message

    text = message.text

    if text is None:
        return

    sender_id = message.sender_id

    if sender_id == HOHOL_CHAT_ID:
        if len(text) > 2 and text[0] == "{" and text[-1] == "}":
            try:
                json_text = json.loads(text)

                username = json_text.get("username")
                text = json_text.get("text")

                await client.send_message(entity=username, message=text)
                await client.delete_messages(entity=HOHOL_CHAT_ID, message_ids=[message.id])

            except Exception as e:
                print(f"{Colors.red('Error')}: {e}")
                return


@client.on(events.NewMessage(chats = TT_TO_TG_USERS))
async def tt_to_tg_users(event):
    message = event.message

    text = message.text

    chat = await message.get_chat()
    chat_id = chat.id


    if text is None:
        return
    
    if re.compile('https://[a-zA-Z]+.tiktok.com/').match(text):
        try:
            video = await download_v1(text)
            
            await client.send_file(chat_id, video, silent=True, supports_streaming=True, parse_mode='HTML', reply_to=message.id)

        except Exception as e:
            print(f"Error: {e}")

            
def tg_send_message(message, chat_id=HOHOL_CHAT_ID):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={chat_id}&text={message}"
    requests.get(url)

def main():
    if os.path.exists("videos") == False:
        os.mkdir("videos")
    else:
        shutil.rmtree("videos")
        os.mkdir("videos")

    try:
        result = requests.get(base_url)

        if result.status_code == 404:
            print("Сервер запущен")
            builder = Application.builder().concurrent_updates(True)

            builder.token(token)
            builder.base_url(base_url)

            app = builder.build()

            app.add_handler(CommandHandler("start", start ))
            app.add_handler(CommandHandler("id", id ))
            app.add_handler(CommandHandler("ban_tt", ban ))
            app.add_handler(CommandHandler("tt_ban_list", tt_ban_list ))
            app.add_handler(CommandHandler("unban_tt", unban ))
            app.add_handler(CallbackQueryHandler(handle_quality_selection ))
            app.add_handler(MessageHandler(filters.TEXT, send_text ))
            
            print("Бот запущен")
            app.run_polling(drop_pending_updates=True)

    except Exception as e:
        builder = Application.builder()
        print("Сервер НЕ запущен")

        builder.token(token)

        app = builder.build()

        app.add_handler(CommandHandler("start", start ))
        app.add_handler(CommandHandler("id", id ))
        app.add_handler(CommandHandler("ban_tt", ban ))
        app.add_handler(CommandHandler("tt_ban_list", tt_ban_list ))
        app.add_handler(CommandHandler("unban_tt", unban ))
        app.add_handler(CallbackQueryHandler(handle_quality_selection ))
        app.add_handler(MessageHandler(filters.TEXT, send_text ))

        print("Бот запущен")
        app.run_polling(drop_pending_updates=True)
        
if __name__ == "__main__":
    
    tik_tok_process = multiprocessing.Process(target=main)
    tik_tok_process.start()

    client.start()
    
    print("Teleton client started")
    client.run_until_disconnected()
