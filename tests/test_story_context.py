import unittest
from unittest.mock import patch

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.core.story_context import build_generation_payload, build_story_context, character_appears_in_shot
from app.models.story import Story
from app.schemas.storyboard import AudioReference, CameraSetup, Shot, VisualElements
from app.services import story_repository as repo
from app.services.story_context_service import prepare_story_context, _parse_json
from app.services.storyboard import parse_script_to_storyboard


class StoryContextTests(unittest.TestCase):
    def test_build_story_context_and_payload_preserve_split_prompts(self):
        story = {
            "art_style": "cinematic watercolor",
            "genre": "古风",
            "selected_setting": "江南水乡，临河茶馆，细雨薄雾，木窗与灯笼营造出潮湿古镇气息。",
            "characters": [
                {
                    "name": "李明",
                    "role": "主角",
                    "description": "25岁青年男子，黑色短发，身形清瘦，穿着深蓝长衫，神情沉稳。",
                }
            ],
            "character_images": {
                "李明": {
                    "prompt": "Character portrait of 李明, clean background, studio lighting, dramatic portrait",
                    "visual_dna": "25-year-old man, short black hair, slim build",
                }
            },
            "meta": {
                "scene_style_cache": [
                    {
                        "keywords": [],
                        "image_extra": "jiangnan river town, wet stone paths, warm lantern glow",
                        "video_extra": "jiangnan river town, warm lantern glow, wet stone paths",
                    }
                ]
            },
        }
        shot = Shot(
            shot_id="scene1_shot1",
            storyboard_description="李明站在茶馆门口，准备推门进入。",
            camera_setup=CameraSetup(shot_size="MS", camera_angle="Eye-level", movement="Static"),
            visual_elements=VisualElements(
                subject_and_clothing="李明穿着深蓝长衫，站在门口",
                action_and_expression="右手抬起准备推门，目光看向屋内",
                environment_and_props="临河茶馆木门、雨雾和灯笼",
                lighting_and_color="柔和阴天自然光，暖色灯笼补光",
            ),
            image_prompt="Medium shot. Li Ming in a dark blue robe pauses at the teahouse doorway, hand lifted toward the wooden door. River-town rain mist and lanterns frame the still composition.",
            final_video_prompt="Medium shot. Static camera. Li Ming pushes the wooden door inward and steps into the teahouse. Rain mist and lantern glow stay stable around the entrance.",
            last_frame_prompt="Medium shot. Li Ming has just entered the teahouse, one hand still on the opened wooden door, lantern glow behind him.",
            audio_reference=AudioReference(type="dialogue", content="到了。"),
        )

        ctx = build_story_context(story)
        payload = build_generation_payload(shot, ctx)

        self.assertIn("Visual DNA", ctx.clean_character_section)
        self.assertNotIn("studio lighting", ctx.clean_character_section.lower())
        self.assertIn("Character anchor:", payload["image_prompt"])
        self.assertIn("Li Ming pushes the wooden door inward", payload["final_video_prompt"])
        self.assertIn("cinematic watercolor", payload["image_prompt"])
        self.assertIn("cinematic watercolor", payload["final_video_prompt"])
        self.assertIn("jiangnan river town", payload["image_prompt"])
        self.assertNotIn("江南水乡", payload["image_prompt"])
        self.assertNotIn("江南水乡", payload["final_video_prompt"])
        self.assertIn("last_frame_prompt", payload)
        self.assertNotEqual(payload["image_prompt"], payload["final_video_prompt"])

    def test_character_matching_avoids_substring_false_positive(self):
        story = {
            "characters": [
                {"name": "Ann", "role": "support", "description": "short hair"},
                {"name": "Anna", "role": "lead", "description": "long hair"},
            ],
            "meta": {
                "character_appearance_cache": {
                    "Ann": {"negative_prompt": "ann-only"},
                    "Anna": {"negative_prompt": "anna-only"},
                }
            },
        }
        shot = {
            "storyboard_description": "Anna opens the door and looks back.",
            "negative_prompt": "low quality, blur",
        }

        ctx = build_story_context(story)
        payload = build_generation_payload(shot, ctx)

        self.assertFalse(character_appears_in_shot("Ann", shot))
        self.assertTrue(character_appears_in_shot("Anna", shot))
        self.assertEqual(payload["negative_prompt"], "low quality, blur, anna-only")

    def test_character_matching_prefers_structured_names(self):
        shot = {
            "storyboard_description": "",
            "characters": [{"name": "Li Ming"}],
        }
        self.assertTrue(character_appears_in_shot("Li Ming", shot))
        self.assertFalse(character_appears_in_shot("Li", shot))


class ParseStoryboardOverrideTests(unittest.IsolatedAsyncioTestCase):
    async def test_parse_script_to_storyboard_uses_character_section_override(self):
        response = """
        [
          {
            "shot_id": "scene1_shot1",
            "storyboard_description": "李明推门进入茶馆。",
            "camera_setup": {"shot_size": "MS", "camera_angle": "Eye-level", "movement": "Static"},
            "visual_elements": {
              "subject_and_clothing": "李明，深蓝长衫",
              "action_and_expression": "推门进入",
              "environment_and_props": "茶馆木门与灯笼",
              "lighting_and_color": "暖色灯笼与阴天自然光"
            },
            "image_prompt": "Medium shot. Li Ming pauses at the wooden teahouse doorway.",
            "final_video_prompt": "Medium shot. Static camera. Li Ming pushes open the wooden door and enters the teahouse."
          }
        ]
        """.strip()

        class FakeProvider:
            def __init__(self):
                self.messages = []

            async def complete_messages_with_usage(self, messages, system: str = "", temperature: float = 0.3, **kwargs):
                self.messages = messages
                return response, {"prompt_tokens": 10, "completion_tokens": 5}

        fake = FakeProvider()
        with patch("app.services.storyboard.get_llm_provider", return_value=fake):
            shots, usage = await parse_script_to_storyboard(
                "【环境】茶馆门口\n【画面】李明推门进入。",
                provider="openai",
                character_info={
                    "characters": [{"name": "李明", "role": "主角", "description": "青年男子"}],
                    "character_images": {"李明": {"prompt": "Character portrait, studio lighting"}},
                },
                character_section_override="## Character Reference\n- 李明：Visual DNA only",
            )

        self.assertEqual(len(shots), 1)
        self.assertEqual(usage["prompt_tokens"], 10)
        flattened = "\n".join(message.get("content", "") for message in fake.messages)
        self.assertIn("Visual DNA only", flattened)
        self.assertNotIn("studio lighting", flattened.lower())


class StoryContextPreparationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_prepare_story_context_extracts_and_persists_caches(self):
        async with self.session_factory() as session:
            await repo.save_story(
                session,
                "story-ctx-prepare",
                {
                    "idea": "test",
                    "genre": "历史",
                    "tone": "沉稳",
                    "selected_setting": "江南古镇，临河茶馆，木窗灯笼，细雨薄雾。",
                    "characters": [
                        {
                            "name": "李明",
                            "role": "主角",
                            "description": "25岁青年男子，黑色短发，身形清瘦，穿着深蓝长衫。",
                        }
                    ],
                    "meta": {},
                },
            )

            class FakeProvider:
                async def complete_messages_with_usage(self, messages, system: str = "", temperature: float = 0.3, **kwargs):
                    if "stable visual anchors" in system:
                        return (
                            """
                            {
                              "characters": {
                                "李明": {
                                  "body": "young man, short black hair, slim build",
                                  "clothing": "dark blue robe",
                                  "negative_prompt": "modern clothing"
                                }
                              }
                            }
                            """.strip(),
                            {"prompt_tokens": 120, "completion_tokens": 40},
                        )
                    return (
                        """
                        {
                          "styles": [
                            {
                              "keywords": ["teahouse", "river town"],
                              "image_extra": "jiangnan river town, wooden teahouse, rain mist, warm lantern glow",
                              "video_extra": "jiangnan river town, rain mist, warm lantern glow",
                              "negative_prompt": "cars, neon signs"
                            }
                          ]
                        }
                        """.strip(),
                        {"prompt_tokens": 80, "completion_tokens": 30},
                    )

            with patch("app.services.story_context_service.get_llm_provider", return_value=FakeProvider()):
                story, ctx = await prepare_story_context(
                    session,
                    "story-ctx-prepare",
                    provider="openai",
                    model="gpt-4o-mini",
                    api_key="test-key",
                    base_url="https://example.com/v1",
                )

            self.assertIsNotNone(ctx)
            self.assertEqual(
                story["meta"]["character_appearance_cache"]["李明"]["body"],
                "young man, short black hair, slim build",
            )
            self.assertEqual(
                story["character_images"]["李明"]["visual_dna"],
                "young man, short black hair, slim build",
            )
            self.assertEqual(
                story["meta"]["scene_style_cache"][0]["video_extra"],
                "jiangnan river town, rain mist, warm lantern glow",
            )
            shot = {
                "shot_id": "scene1_shot1",
                "storyboard_description": "李明在茶馆门口停下。",
                "image_prompt": "Medium shot. Li Ming pauses at the teahouse doorway.",
                "final_video_prompt": "Medium shot. Static camera. Li Ming pushes the wooden door inward.",
            }
            payload = build_generation_payload(shot, ctx)
            self.assertIn("jiangnan river town", payload["image_prompt"])
            self.assertIn("modern clothing", payload["negative_prompt"])


class StoryContextServiceParsingTests(unittest.TestCase):
    def test_parse_json_extracts_first_fenced_block(self):
        content = """
        Intro text
        ```json
        {"characters": {"Li Ming": {"body": "short black hair"}}}
        ```
        ```json
        {"ignored": true}
        ```
        """.strip()

        parsed = _parse_json(content)

        self.assertEqual(parsed["characters"]["Li Ming"]["body"], "short black hair")


class StoryRepositoryHelperTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_meta_cache_helpers_preserve_other_meta_keys(self):
        async with self.session_factory() as session:
            await repo.save_story(
                session,
                "story-cache-test",
                {"idea": "test", "genre": "古风", "tone": "沉稳", "meta": {"theme": "雨夜古镇"}},
            )
            await repo.upsert_story_meta_cache(
                session,
                "story-cache-test",
                "character_appearance_cache",
                {"李明": {"body": "short black hair", "clothing": "dark blue robe"}},
            )

            story = await repo.get_story(session, "story-cache-test")
            self.assertEqual(story["meta"]["theme"], "雨夜古镇")
            self.assertIn("character_appearance_cache", story["meta"])

            await repo.invalidate_story_consistency_cache(session, "story-cache-test", appearance=True)
            updated_story = await repo.get_story(session, "story-cache-test")
            self.assertEqual(updated_story["meta"]["theme"], "雨夜古镇")
            self.assertNotIn("character_appearance_cache", updated_story["meta"])


if __name__ == "__main__":
    unittest.main()
