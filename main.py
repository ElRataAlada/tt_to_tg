import os
import re

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters, Application

import asyncio
from concurrent.futures import ThreadPoolExecutor
import requests
from parsel import Selector
import shutil
import os
import time
import re
import json
import io
import PIL.Image as Image
from moviepy.editor import AudioFileClip, VideoFileClip, concatenate_videoclips, concatenate_audioclips

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

headers = {
'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}

def get_type(url):
  response = requests.get(url, headers=headers)
  new_url = response.url

  if new_url.find('video') != -1:
    content_type = "video"
  else:
    content_type = "photo"
    
  return content_type

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

        content_type = get_type(link)

        file_name = "videos/" + link.split("/")[-1] 

        with requests.Session() as s:
            response = s.get("https://tmate.cc/", headers=headers)

            selector = Selector(response.text)
            token = selector.css('input[name="token"]::attr(value)').get()
            data = {'url': link, 'token': token}

            response = s.post('https://tmate.cc/action', headers=headers, data=data).json()["data"]

            selector = Selector(text=response)

            if content_type == "video":
              download_link_index = 0
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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Отправь ссылку на видео с tiktok и получи видео")

async def id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Твой id: `{update.effective_user.id}`\nID чата: `{update.effective_chat.id}`", parse_mode="MarkdownV2")

async def send_text_inner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    sender_username = message.from_user.username
    chat_id = update.effective_chat.id
    
    if chat_id == 7344659725 and message.text.split(" ")[0] == ".к":
        reply = message.reply_to_message
        await context.bot.copy_message(chat_id="-1002005871510", from_chat_id=7344659725, message_id=reply.message_id)
        
        return

    elif re.compile('https://[a-zA-Z]+.tiktok.com/').match(message.text):
        print(f"Received: {message.text}")
        index = message.text.find("tiktok.com/") + 9 + len("tiktok.com/") 
        tt_link = message.text[0:index]
        subtext = message.text[index+1:].strip()
        
        try:
            sender_username = message.from_user.username
            bot = context.bot

            chat_id = update.effective_chat.id

            chat_type = update.effective_chat.type

            link = f'<a href="{tt_link}">🔗 Ссылка</a>'

            caption = f'👤 @{sender_username}\n{link}'
            
            if len(subtext) != 0:
              caption = f'💬: {subtext}\n\n👤 @{sender_username}\n{link}'
    
            video = await download_v1(tt_link)

            if chat_type == 'group' or chat_type == 'supergroup':
                await bot.sendVideo(chat_id, video, supports_streaming=True, disable_notification=True, caption=caption, parse_mode='HTML',pool_timeout=200000,connect_timeout=200000,read_timeout=200000,write_timeout=200000)
                await bot.deleteMessage(chat_id, message.message_id)

            elif chat_type == 'private':
                await bot.sendVideo(chat_id, video, supports_streaming=True, disable_notification=True, reply_to_message_id=message.message_id,pool_timeout=200000,connect_timeout=200000,read_timeout=200000,write_timeout=200000)

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
        app.add_handler(MessageHandler(filters.TEXT, send_text ))

        print("Бот запущен")
        app.run_polling(drop_pending_updates=True)
        
if __name__ == "__main__":
    
    tik_tok_process = multiprocessing.Process(target=main)
    tik_tok_process.start()

    client.start()
    
    print("Teleton client started")
    client.run_until_disconnected()
