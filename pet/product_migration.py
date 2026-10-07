"""Configuration migration for the qilin product; no network or secret reads."""
from __future__ import annotations


def _old_vendor(value: object) -> bool:
    value = str(value or '').casefold()
    return any(word in value for word in ('deepseek', '深度求索'))


def _old_builtin_path(value: object) -> bool:
    path = str(value or '').replace('\\', '/').casefold().rstrip('/')
    return '/assets/big_blue_fat_fish' in '/' + path


def migrate_qilin_product(data: dict) -> None:
    """Remove retired providers and services, while keeping unrelated preferences."""
    from . import catalog

    if catalog._DEPLOYED_CHARACTER == 'qilin' and data.get('character') == 'shenshen':
        data['character'] = 'qilin'
    chat = data.get('chat')
    if isinstance(chat, dict) and isinstance(chat.get('providers'), dict):
        providers = chat['providers']
        for pid, provider in list(providers.items()):
            if isinstance(provider, dict) and (_old_vendor(pid) or any(_old_vendor(provider.get(k)) for k in
                    ('name', 'base_url', 'model', 'vision_base_url', 'vision_model'))):
                del providers[pid]
        if not providers:
            from .config import _default_chat_data
            providers.update(_default_chat_data()['providers'])
        if chat.get('active_provider') not in providers:
            chat['active_provider'] = next(iter(providers))
    for key, value in (
        ('harness_autostart', False), ('click_show_balance', False),
        ('balance_refresh_minutes', 0), ('agent_cost_enabled', False),
    ):
        data[key] = value
    links = data.get('agent_link')
    if isinstance(links, dict):
        links['dsh'] = False
    for key in ('chat_background', 'modern_chat_background'):
        if str(data.get(key, '')).startswith('builtin:whale'):
            data[key] = 'builtin:qilin'
    if _old_builtin_path(data.get('self_talk_image_dir')):
        data['self_talk_image_dir'] = 'assets/qilin_memes'
    texts = data.get('self_talk_texts')
    if isinstance(texts, list):
        data['self_talk_texts'] = [
            '瑞麟给你加油。' if text == '欧鲸鲸……' else
            '麒麟来陪你啦。' if _old_vendor(text) else text
            for text in texts
        ]
    aliases = data.get('character_aliases')
    if isinstance(aliases, dict):
        for character_id, alias in list(aliases.items()):
            if _old_vendor(alias):
                del aliases[character_id]
    egg = data.get('menu_easter_egg')
    if isinstance(egg, dict):
        if _old_builtin_path(egg.get('avatar')):
            egg['avatar'] = 'assets/qilin_memes/praise.png'
        if _old_builtin_path(egg.get('image_dir')):
            egg['image_dir'] = 'assets/qilin_memes'
        if egg.get('title') == '厉害了我的鲸' or _old_vendor(egg.get('title')):
            egg['title'] = '麒麟表情包'
