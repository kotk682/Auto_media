# 共享内存存储，mock 和真实 LLM 均使用
_stories = {}


def save_story(story_id: str, data: dict):
    _stories[story_id] = {**_stories.get(story_id, {}), **data}


def get_story(story_id: str) -> dict:
    return _stories.get(story_id, {})
