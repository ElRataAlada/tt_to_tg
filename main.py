
from telebot.types import InputMediaPhoto
import os
import re
from aiogram.utils.markdown import hlink

from telegram import Update 
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters, Application

import requests
from parsel import Selector
import argparse
import os
from tqdm import tqdm
import re
import json
import jmespath

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
    if 'vm.tiktok.com' in url:
        response = requests.get(url, headers=headers)
        url = response.url

    username_pattern = r"@([A-Za-z0-9_.]+)"
    content_type_pattern = r"/(video|photo)/(\d+)"

    username_match = re.search(username_pattern, url)
    username = username_match.group(0)

    content_type_match = re.search(content_type_pattern, url)
    content_type = content_type_match.group(1)
    video_id = content_type_match.group(2)

    return username, video_id, content_type


def extract_metadata(url):
    response = requests.get(url, headers=headers)
    html = Selector(response.text)
    account_data = json.loads(html.xpath('//*[@id="__UNIVERSAL_DATA_FOR_REHYDRATION__"]/text()').get())
    data = account_data["__DEFAULT_SCOPE__"]["webapp.video-detail"]["itemInfo"]["itemStruct"]

    expression = """
    {
        id: id,
        description: desc,
        createTime: createTime,
        video: video.{height: height, width: width, duration: duration, ratio: ratio, bitrate: bitrate, format: format, codecType: codecType, definition: definition},
        author: author.{id: id, uniqueId: uniqueId, nickname: nickname, signature: signature},
        music: music.{id: id, title: title, authorName: authorName, duration: duration},
        stats: stats,
        suggestedWords: suggestedWords,
        diversificationLabels: diversificationLabels,
        contents: contents[].{textExtra: textExtra[].{hashtagName: hashtagName}}
    }
    """

    parsed_data = jmespath.search(expression, data)
    return parsed_data


def downloader(file_name, link, response, extension):
    file_size = int(response.headers.get("content-length", 0))
    folder_name, _ , content_type = extract_video_id(link)

    if os.path.exists(folder_name):
        for file in os.listdir(folder_name):
            os.remove(f"{folder_name}/{file}")

        os.rmdir(folder_name)

    if not os.path.exists(folder_name):
        os.mkdir(folder_name)

    with open(f"{folder_name}/{file_name}.{extension}", 'wb') as file, tqdm(
        total=file_size,
        unit='iB',
        unit_scale=True,
        unit_divisor=1024,
        bar_format='{percentage:3.0f}%|{bar:20}{r_bar}{desc}', colour='green', desc=f"[{file_name}]"
    ) as progress_bar:
        for data in response.iter_content(chunk_size=1024):
            size = file.write(data)
            progress_bar.update(size)

    if args.save_metadata and content_type != "photo":
        path = f"{folder_name}/metadata"

        if not os.path.exists(path):
            os.mkdir(path)

        metadata = extract_metadata(link)

        with open(f'{path}/{file_name}.json', 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=4, ensure_ascii=False)

    return folder_name



def download_v2(link):
    headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0',
    'Sec-Fetch-Site': 'same-origin',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Origin': 'https://musicaldown.com',
    'Connection': 'keep-alive',
    'Referer': 'https://musicaldown.com/en?ref=more',
    }


    _, file_name, content_type = extract_video_id(link)

    with requests.Session() as s:
        try:
            file_name = None
            r = s.get("https://musicaldown.com/en", headers=headers)

            selector = Selector(text=r.text)

            token_a = selector.xpath('//*[@id="link_url"]/@name').get()
            token_b = selector.xpath('//*[@id="submit-form"]/div/div[1]/input[2]/@name').get()
            token_b_value = selector.xpath('//*[@id="submit-form"]/div/div[1]/input[2]/@value').get()

            data = {
                token_a: link,
                token_b: token_b_value,
                'verify': '1',
            }

            response = s.post('https://musicaldown.com/download', headers=headers, data=data)

            selector = Selector(text=response.text)

            if content_type == "video":
                watermark = selector.xpath('/html/body/div[2]/div/div[3]/div[2]/a[4]/@href').get()
                no_watermark = selector.xpath('/html/body/div[2]/div/div[3]/div[2]/a[1]/@href').get()

                download_link = watermark if args.watermark else no_watermark

                response = s.get(download_link, stream=True, headers=headers)

                folder_name = downloader(file_name, link, response, extension="mp4")
            else:
                download_links = selector.xpath('//div[@class="card-image"]/img/@src').getall()
                
                for index, download_link in enumerate(download_links):
                    response = s.get(download_link, stream=True, headers=headers)
                    folder_name = downloader(f"{file_name}_{index}", link, response, extension="jpeg")

            return folder_name, content_type

        except Exception as e:
            print(f"\033[91merror\033[0m: {link} - {str(e)}")
            with open("errors.txt", 'a') as error_file:
                error_file.write(link + "\n")


def download_v1(link):
    headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:107.0) Gecko/20100101 Firefox/107.4',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Origin': 'https://tmate.cc',
    'Connection': 'keep-alive',
    'Referer': 'https://tmate.cc/',
    'Sec-Fetch-Site': 'same-origin',
    }

    _, file_name, content_type = extract_video_id(link)

    with requests.Session() as s:
        try:
            response = s.get("https://tmate.cc/", headers=headers)

            selector = Selector(response.text)
            token = selector.css('input[name="token"]::attr(value)').get()
            data = {'url': link, 'token': token}

            response = s.post('https://tmate.cc/action', headers=headers, data=data).json()["data"]
            
            selector = Selector(text=response)

            if content_type == "video":
                download_link_index = 3 if args.watermark else 0
                download_link = selector.css('.downtmate-right.is-desktop-only.right a::attr(href)').getall()[download_link_index]

                response = s.get(download_link, stream=True, headers=headers)

                downloader(file_name, link, response, extension="mp4")
            else:
                download_links = selector.css('.card-img-top::attr(src)').getall()
                for index, download_link in enumerate(download_links):
                    response = s.get(download_link, stream=True, headers=headers)

                    downloader(f"{file_name}_{index}", link, response, extension="jpeg")

        except Exception:
            print(f"\033[91merror\033[0m: {link}")
            with open("errors.txt", 'a') as error_file:
                error_file.write(link + "\n")







async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Отправь ссылку на видео с tiktok и получи видео")


async def send_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    sender_username = message.from_user.username
    bot = context.bot

    chat_id = update.effective_chat.id
    link = hlink('Cсылка на видео', message.text)
    
    if re.compile('https://[a-zA-Z]+.tiktok.com/').match(message.text):

        try:
            tiktok_link = message.text

            folder_name, content_type = download_v2(tiktok_link)

            if content_type == "video":
                filename = os.listdir(folder_name)[0]   

                with open(f'{folder_name}/{filename}', 'rb') as video:
                    caption = f'Отправил: @{sender_username}\n\n{link}'
                    await bot.sendVideo(chat_id, video, supports_streaming=True, disable_notification=None, caption=caption, parse_mode='HTML')

                os.remove(f'{folder_name}/{filename}')
                os.rmdir(f'{folder_name}')

            elif content_type == "photo":
                photos_list = [open(f'{folder_name}/{photo}', 'rb') for photo in os.listdir(folder_name)]

                photos = [InputMediaPhoto(media=photo) for photo in photos_list]

                caption = f'Отправил: @{sender_username}\n\n{link}'

                await bot.sendMediaGroup(chat_id, photos, disable_notification=None)
                await bot.sendMessage(chat_id, caption, parse_mode='HTML')

                for photo in photos_list:
                    photo.close()

                for photo in os.listdir(folder_name):
                    os.remove(f'{folder_name}/{photo}')

                os.rmdir(f'{folder_name}')

            await bot.deleteMessage(chat_id, message.message_id)

        except Exception as e:
            print(e)

            await bot.sendMessage(MY_ID, f"Ошибка: {e}")


MY_ID = 543015172

token = '7458133965:AAEpmdxPQbAJnsSOcmb7QPjco40w6wuUWjk'
base_url = 'http://192.168.31.153:1488/bot'

if __name__ == "__main__":

    while True:
        try:
            result = requests.get(base_url)

            if result.status_code != 404:
                print("Сервер не запущен")
                raise Exception("Сервер не запущен")

            builder = Application.builder()

            builder.token(token)
            builder.base_url(base_url)

            app = builder.build()

            app.add_handler(CommandHandler("start", start))
            app.add_handler(MessageHandler(filters.TEXT, send_text))

            print("Бот запущен")
            app.run_polling(timeout=1, drop_pending_updates=True)

            print("Сервер запущен")

            if requests.get(base_url).status_code != 404:
                raise Exception("Сервер не запущен")
        
        except Exception as e:
            print("Сервер не запущен\nПерехожу в режим работы через телеграмм\n\n")
            
            builder = Application.builder()

            builder.token(token)

            app = builder.build()

            app.add_handler(CommandHandler("start", start))
            app.add_handler(MessageHandler(filters.TEXT, send_text))

            print("Бот запущен")
            app.run_polling(timeout=1, drop_pending_updates=True)