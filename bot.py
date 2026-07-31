import os
import requests
import re
import pytesseract
from PIL import Image
import io

# ID ВАШИХ ГРУПП
GROUP_SOURCE = -101295534  
GROUP_TARGET = -228796982  

VK_TOKEN = os.environ.get('VK_TOKEN')
API_VERSION = '5.131'

def check_url_for_erid(url):
    """Маскируется под браузер, переходит по ссылке и ищет erid везде"""
    try:
        if not url.startswith('http'): url = 'https://' + url
        # Притворяемся настоящим человеком, чтобы сайты не блокировали бота
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'}
        
        r = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        final_url = r.url.lower()
        
        # 1. Проверяем саму финальную ссылку
        if 'erid' in final_url: return True
        
        # 2. ХИТРОСТЬ: редирект бывает через JS. Ищем erid прямо в коде страницы!
        if 'erid' in r.text.lower(): return True
    except:
        pass
    return False

def check_image_for_erid(photo_url):
    """Скачивает картинку и ищет erid"""
    try:
        r = requests.get(photo_url, timeout=10)
        img = Image.open(io.BytesIO(r.content))
        text_on_image = pytesseract.image_to_string(img, lang='eng+rus').lower()
        if 'erid' in text_on_image or 'ерид' in text_on_image:
            return True
    except:
        pass
    return False

def get_largest_photo_url(photo_item):
    sizes = photo_item.get('sizes', [])
    if not sizes: return None
    best_size = max(sizes, key=lambda s: s.get('width', 0) * s.get('height', 0))
    return best_size.get('url')

def has_erid(post):
    # 1. Собираем ВООБЩЕ ВЕСЬ текст (включая скрытые описания ссылок)
    all_text = post.get('text', '')
    
    for att in post.get('attachments', []):
        if att['type'] == 'link':
            link = att['link']
            # Склеиваем заголовок, описание и саму ссылку
            all_text += f" {link.get('url', '')} {link.get('title', '')} {link.get('description', '')} {link.get('caption', '')}"
            
    all_text = all_text.lower()
    
    # ПРОВЕРКА 1: Текст
    if 'erid' in all_text or 'ерид' in all_text:
        print("Нашли erid в тексте или скрытом описании!")
        return True

    # ПРОВЕРКА 2: Разворачиваем все короткие ссылки
    urls_in_text = re.findall(r'(?:https?://|vk\.cc/|clck\.ru/|ozon\.ru/t/)[^\s]+', all_text)
    for url in urls_in_text:
        url = url.rstrip('.,!?"\')')
        if check_url_for_erid(url):
            print(f"Нашли erid внутри зашифрованной ссылки: {url}")
            return True

    # ПРОВЕРКА 3: Все картинки (и обычные, и превью от ссылок)
    for att in post.get('attachments', []):
        photo_url = None
        if att['type'] == 'photo':
            photo_url = get_largest_photo_url(att['photo'])
        elif att['type'] == 'link' and 'photo' in att['link']:
            # Достаем картинку из превью ссылки!
            photo_url = get_largest_photo_url(att['link']['photo'])
            
        if photo_url and check_image_for_erid(photo_url):
            print("Нашли erid на картинке!")
            return True
            
    return False

def get_attachments_string(post):
    attachments = []
    for att in post.get('attachments', []):
        att_type = att['type']
        if att_type in ['photo', 'video', 'audio', 'doc']:
            item = att[att_type]
            att_str = f"{att_type}{item['owner_id']}_{item['id']}"
            if 'access_key' in item:
                att_str += f"_{item['access_key']}"
            attachments.append(att_str)
    return ','.join(attachments)

def main():
    try:
        with open('last_post_id.txt', 'r') as f:
            last_id = int(f.read().strip())
    except:
        last_id = 0

    response = requests.get('https://api.vk.com/method/wall.get', params={
        'owner_id': GROUP_SOURCE, 'count': 10, 'access_token': VK_TOKEN, 'v': API_VERSION
    }).json()

    if 'error' in response:
        print("Ошибка:", response['error'])
        return

    posts = response['response']['items']

    if last_id == 0 and posts:
        with open('last_post_id.txt', 'w') as f:
            f.write(str(posts[0]['id']))
        return
    
    posts = sorted([p for p in posts if p['id'] > last_id], key=lambda x: x['id'])
    new_last_id = last_id

    for post in posts:
        if has_erid(post) or post.get('marked_as_ads'):
            new_last_id = max(new_last_id, post['id'])
            continue

        post_data = {
            'owner_id': GROUP_TARGET,
            'message': post.get('text', ''),
            'attachments': get_attachments_string(post),
            'from_group': 1,
            'access_token': VK_TOKEN,
            'v': API_VERSION
        }

        post_response = requests.post('https://api.vk.com/method/wall.post', data=post_data).json()
        
        if 'response' in post_response:
            print(f"Пост {post['id']} скопирован.")
            new_last_id = max(new_last_id, post['id'])
        else:
            print("Ошибка:", post_response)
            break

    with open('last_post_id.txt', 'w') as f:
        f.write(str(new_last_id))

if __name__ == "__main__":
    main()
