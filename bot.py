import os
import requests

# ID ВАШИХ ГРУПП
GROUP_SOURCE = -101295534  # anton_kupon (откуда берем)
GROUP_TARGET = -228796982  # skidkich (куда постим)

VK_TOKEN = os.environ.get('VK_TOKEN')
API_VERSION = '5.131'

def has_erid(post):
    text = post.get('text', '').lower()
    if 'erid' in text: return True
    for att in post.get('attachments', []):
        if att['type'] == 'link':
            url = att['link'].get('url', '').lower()
            if 'erid' in url: return True
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

    # Защита при самом первом запуске
    if last_id == 0 and posts:
        with open('last_post_id.txt', 'w') as f:
            f.write(str(posts[0]['id']))
        print("Первый запуск: сохранили ID последнего поста. Бот готов к работе!")
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
            print("Ошибка публикации:", post_response)
            break

    with open('last_post_id.txt', 'w') as f:
        f.write(str(new_last_id))

if __name__ == "__main__":
    main()
