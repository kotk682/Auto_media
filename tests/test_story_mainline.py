import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.core.story_assets import build_character_asset_record
from app.routers.story import finalize_script
from app.services import story_repository as repo
from app.services.story_mock import mock_generate_outline
from app.services.story_llm import (
    _ensure_world_building_question_options,
    _build_apply_chat_history_text,
    _merge_characters,
    analyze_idea,
    apply_chat,
    generate_outline,
    generate_script,
    refine,
    world_building_start,
    world_building_turn,
)


class WorldBuildingQuestionOptionTests(unittest.TestCase):
    def test_pads_missing_world_building_options_without_rewriting_question(self):
        question = {
            "type": "options",
            "text": "故事发生在哪个舞台？",
            "options": ["现代都市（豪门 / 职场 / 校园）"],
            "dimension": "舞台选择",
            "extra": "keep-me",
        }

        normalized = _ensure_world_building_question_options(question)

        self.assertEqual(normalized["text"], question["text"])
        self.assertEqual(normalized["dimension"], question["dimension"])
        self.assertEqual(normalized["extra"], "keep-me")
        self.assertEqual(
            normalized["options"],
            [
                "现代都市（豪门 / 职场 / 校园）",
                "古代架空（宫廷 / 江湖 / 世家）",
                "玄幻异能（都市异能 / 修仙 / 末世）",
            ],
        )

    def test_extracts_displayable_options_from_object_list(self):
        question = {
            "type": "options",
            "text": "主要人物有几位？",
            "options": [
                {"label": "2位：男女主 CP，双强对决"},
                {"text": "3位：三角关系，情感纠葛"},
            ],
            "dimension": "人物规模",
        }

        normalized = _ensure_world_building_question_options(question)

        self.assertEqual(
            normalized["options"],
            [
                "2位：男女主 CP，双强对决",
                "3位：三角关系，情感纠葛",
                "4-5位：群像叙事，多线并行",
            ],
        )


class StoryLlmMergeTests(unittest.TestCase):
    def test_merge_characters_rejects_incoming_character_without_id(self):
        with self.assertRaises(ValueError):
            _merge_characters(
                [{"id": "char_li_ming", "name": "Li Ming", "role": "lead", "description": "young man"}],
                [{"name": "Li Ming", "role": "lead", "description": "updated"}],
            )


class StoryOutlineValidationTests(unittest.IsolatedAsyncioTestCase):
    async def test_generate_outline_rejects_incomplete_outline_payload(self):
        blueprint_response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            '{"meta":{"title":"标题","genre":"类型","episodes":6,"theme":"主题","logline":"一句话冲突","visual_tone":"冷峻"},'
                            '"characters":[{"name":"主角","role":"主角","description":"黑发，外冷内烈。"}],'
                            '"relationships":[{"source":"主角","target":"反派","label":"宿敌"}],'
                            '"season_plan":{"episode_arcs":['
                            '{"episode":1,"arc":"建立主冲突"},'
                            '{"episode":2,"arc":"矛盾升级"},'
                            '{"episode":3,"arc":"局势失控"},'
                            '{"episode":4,"arc":"真相逼近"},'
                            '{"episode":5,"arc":"决战前夜"},'
                            '{"episode":6,"arc":"完成收束"}'
                            '],"location_glossary":["天台"],"tone_rules":["强冲突"]}}'
                        )
                    )
                )
            ],
            usage=None,
        )
        invalid_batch_response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"outline":[{"episode":1,"title":"第一集","summary":"摘要","beats":["Beat 1"],"scene_list":["Scene 1"]}]}'
                    )
                )
            ],
            usage=None,
        )
        valid_batch_response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            '{"outline":['
                            '{"episode":4,"title":"第四集","summary":"摘要4","beats":["Beat 4"],"scene_list":["Scene 4"]},'
                            '{"episode":5,"title":"第五集","summary":"摘要5","beats":["Beat 5"],"scene_list":["Scene 5"]},'
                            '{"episode":6,"title":"第六集","summary":"摘要6","beats":["Beat 6"],"scene_list":["Scene 6"]}'
                            ']}'
                        )
                    )
                )
            ],
            usage=None,
        )

        async def fake_create(*, model, messages):
            prompt = messages[0]["content"]
            if "全局蓝图（blueprint）" in prompt:
                return blueprint_response
            if "本次只允许生成这些集数：1, 2, 3" in prompt:
                return invalid_batch_response
            if "本次只允许生成这些集数：4, 5, 6" in prompt:
                return valid_batch_response
            raise AssertionError(f"Unexpected prompt: {prompt}")

        fake_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=AsyncMock(side_effect=fake_create))
            )
        )
        save_story = AsyncMock()
        invalidate_cache = AsyncMock()

        with (
            patch("app.services.story_llm._make_client", return_value=fake_client),
            patch("app.services.story_llm.settings.outline_generation_concurrency", 2),
            patch("app.services.story_llm.repo.save_story", new=save_story),
            patch("app.services.story_llm.repo.invalidate_story_consistency_cache", new=invalidate_cache),
        ):
            with self.assertRaises(HTTPException) as exc_info:
                await generate_outline(
                    "story-invalid-outline",
                    selected_setting="新的世界观设定",
                    db=object(),
                    api_key="fake-key",
                    provider="qwen",
                    model="qwen-max",
                )

        self.assertEqual(exc_info.exception.status_code, 502)
        self.assertIn("outline 无效", exc_info.exception.detail)
        save_story.assert_not_awaited()
        invalidate_cache.assert_not_awaited()

    def test_build_apply_chat_history_text_keeps_only_relevant_ai_signal(self):
        history_text = _build_apply_chat_history_text(
            "character",
            [
                {"role": "user", "text": "让她更强势一点"},
                {
                    "role": "ai",
                    "text": "当前角色修改：强化她的压迫感与掌控欲\n对剧情的影响：会让冲突更早爆发",
                },
            ],
        )

        self.assertIn("用户: 让她更强势一点", history_text)
        self.assertIn("AI: 当前角色修改：强化她的压迫感与掌控欲", history_text)
        self.assertNotIn("对剧情的影响", history_text)


class StoryMockTests(unittest.IsolatedAsyncioTestCase):
    async def test_mock_generate_outline_always_returns_dict_meta(self):
        fake_db = object()
        with patch("app.services.story_mock.repo.save_story", new=AsyncMock()) as save_story_mock:
            with patch(
                "app.services.story_mock.repo.get_story",
                new=AsyncMock(return_value={"meta": None, "characters": [], "relationships": [], "outline": []}),
            ):
                result = await mock_generate_outline("story-mock-outline-test", "setting", db=fake_db)

        save_story_mock.assert_awaited_once()
        self.assertEqual(result["meta"], {})


class StoryMainlineFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.debug_patch = patch("app.services.story_llm.settings.debug", True)
        self.debug_patch.start()
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self):
        self.debug_patch.stop()
        await self.engine.dispose()

    async def test_analyze_idea_persists_seed_story(self):
        async with self.session_factory() as session:
            result = await analyze_idea(
                "失意书生在雨夜古镇捡到一块会说话的玉佩。",
                "古风",
                "沉稳",
                db=session,
                api_key="",
            )
            story = await repo.get_story(session, result["story_id"])

        self.assertEqual(story["idea"], "失意书生在雨夜古镇捡到一块会说话的玉佩。")
        self.assertEqual(story["genre"], "古风")
        self.assertEqual(story["tone"], "沉稳")
        self.assertGreaterEqual(len(result["suggestions"]), 1)

    async def test_world_building_outline_script_and_finalize_run_in_order(self):
        async with self.session_factory() as session:
            start = await world_building_start("古镇茶馆中的命运重逢", db=session, api_key="")
            story_id = start["story_id"]

            turn = start
            for idx in range(6):
                turn = await world_building_turn(
                    story_id,
                    answer=f"第{idx + 1}轮选择",
                    db=session,
                    api_key="",
                )

            self.assertEqual(turn["status"], "complete")
            self.assertTrue(turn["world_summary"])

            outline = await generate_outline(
                story_id,
                selected_setting=turn["world_summary"],
                db=session,
                api_key="",
            )
            self.assertEqual(outline["story_id"], story_id)
            self.assertGreaterEqual(len(outline["characters"]), 1)
            self.assertGreaterEqual(len(outline["outline"]), 1)
            self.assertTrue(all(character.get("id") for character in outline["characters"]))
            self.assertTrue(
                all(
                    relationship.get("source_id") and relationship.get("target_id")
                    for relationship in outline["relationships"]
                )
            )

            generated_scenes = []
            async for item in generate_script(story_id, db=session, api_key=""):
                generated_scenes.append(item)
            await repo.save_story(
                session,
                story_id,
                {"scenes": generated_scenes},
            )

            persisted_story = await repo.get_story(session, story_id)
            first_character = persisted_story["characters"][0]
            await repo.save_story(
                session,
                story_id,
                {
                    "character_images": {
                        first_character["id"]: build_character_asset_record(
                            image_url="/media/characters/mainline.png",
                            image_path="media/characters/mainline.png",
                            prompt=f"Standard three-view character turnaround sheet for {first_character['name']}",
                            visual_dna="young woman, long dark hair, cream blouse, charcoal skirt",
                            character_id=first_character["id"],
                            character_name=first_character["name"],
                        )
                    }
                },
            )

            finalized = await finalize_script(story_id, db=session)

        self.assertIn("# 角色信息", finalized["script"])
        self.assertIn("Visual DNA:", finalized["script"])
        self.assertIn("【场景标题】", finalized["script"])
        self.assertIn("【环境锚点】", finalized["script"])
        self.assertIn("【环境】", finalized["script"])
        self.assertIn("【光线】", finalized["script"])
        self.assertIn("【情感标尺】", finalized["script"])
        self.assertIn("【关键道具】", finalized["script"])
        self.assertIn("【画面】", finalized["script"])
        self.assertIn("【动作拆解】", finalized["script"])
        self.assertIn("【", finalized["script"])
        self.assertEqual(finalized["story_id"], story_id)

    async def test_refine_rejects_character_update_missing_id(self):
        async with self.session_factory() as session:
            await repo.save_story(
                session,
                "story-refine-test",
                {
                    "idea": "test",
                    "characters": [
                        {"id": "char_li_ming", "name": "Li Ming", "role": "lead", "description": "young man"},
                    ],
                },
            )

            response = SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content='{"characters":[{"name":"Li Ming","role":"lead","description":"updated"}],"relationships":null,"outline":null,"meta_theme":null}'
                        )
                    )
                ],
                usage=None,
            )
            fake_client = SimpleNamespace(
                chat=SimpleNamespace(
                    completions=SimpleNamespace(create=AsyncMock(return_value=response))
                )
            )

            with patch("app.services.story_llm._make_client", return_value=fake_client):
                with self.assertRaises(HTTPException) as exc:
                    await refine(
                        "story-refine-test",
                        "characters",
                        "update Li Ming",
                        db=session,
                        api_key="fake-key",
                    )

        self.assertEqual(exc.exception.status_code, 502)
        self.assertIn("without a valid id", exc.exception.detail)

    async def test_apply_chat_character_only_updates_description(self):
        async with self.session_factory() as session:
            await repo.save_story(
                session,
                "story-apply-chat-character",
                {
                    "idea": "test",
                    "characters": [
                        {
                            "id": "char_hero",
                            "name": "林晓雨",
                            "role": "女主角",
                            "description": "原始描述",
                        },
                    ],
                    "scenes": [{"episode": 1, "title": "旧剧本", "scenes": [{"scene_number": 1}]}],
                },
            )

            response = SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content='{"name":"被错误改名","role":"女配角","description":"更新后的角色描述"}'
                        )
                    )
                ],
                usage=None,
            )
            fake_client = SimpleNamespace(
                chat=SimpleNamespace(
                    completions=SimpleNamespace(create=AsyncMock(return_value=response))
                )
            )

            with patch("app.services.story_llm._make_client", return_value=fake_client):
                result = await apply_chat(
                    "story-apply-chat-character",
                    "character",
                    chat_history=[
                        SimpleNamespace(role="user", text="让她更强势一点"),
                        SimpleNamespace(role="ai", text="当前角色修改：更强势\n对剧情的影响：推进冲突"),
                    ],
                    current_item={
                        "id": "char_hero",
                        "name": "林晓雨",
                        "role": "女主角",
                        "description": "原始描述",
                    },
                    db=session,
                    api_key="fake-key",
                )

            story = await repo.get_story(session, "story-apply-chat-character")
            character = story["characters"][0]

        self.assertEqual(character["name"], "林晓雨")
        self.assertEqual(character["role"], "女主角")
        self.assertEqual(character["description"], "更新后的角色描述")
        self.assertEqual(story["scenes"], [])
        self.assertEqual(
            result,
            {
                "name": "林晓雨",
                "role": "女主角",
                "description": "更新后的角色描述",
            },
        )

    async def test_apply_chat_logs_safe_warning_when_json_parsing_fails(self):
        async with self.session_factory() as session:
            await repo.save_story(
                session,
                "story-apply-chat-parse-error",
                {
                    "idea": "test",
                    "characters": [
                        {
                            "id": "char_hero",
                            "name": "林晓雨",
                            "role": "女主角",
                            "description": "原始描述",
                        },
                    ],
                },
            )

            response = SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="not-json-response"))],
                usage=None,
            )
            fake_client = SimpleNamespace(
                chat=SimpleNamespace(
                    completions=SimpleNamespace(create=AsyncMock(return_value=response))
                )
            )

            with (
                patch("app.services.story_llm._make_client", return_value=fake_client),
                patch("app.services.story_llm.logger.warning") as warning_mock,
                patch("builtins.print") as print_mock,
            ):
                result = await apply_chat(
                    "story-apply-chat-parse-error",
                    "character",
                    chat_history=[],
                    current_item={
                        "id": "char_hero",
                        "name": "林晓雨",
                        "role": "女主角",
                        "description": "原始描述",
                    },
                    db=session,
                    api_key="fake-key",
                )

        self.assertEqual(result, {})
        print_mock.assert_not_called()
        warning_mock.assert_called_once()
        self.assertIn("Apply chat response JSON parsing failed", warning_mock.call_args.args[0])
        self.assertEqual(warning_mock.call_args.args[1], "story-apply-chat-parse-error")
        self.assertEqual(warning_mock.call_args.args[2], "character")
        self.assertEqual(warning_mock.call_args.args[3], "JSONDecodeError")
        self.assertEqual(warning_mock.call_args.args[4], len("not-json-response"))

    async def test_apply_chat_episode_updates_full_outline_fields(self):
        async with self.session_factory() as session:
            await repo.save_story(
                session,
                "story-apply-chat-episode",
                {
                    "idea": "test",
                    "outline": [
                        {
                            "episode": 1,
                            "title": "旧标题",
                            "summary": "旧摘要",
                            "beats": ["旧节拍1", "旧节拍2"],
                            "scene_list": ["Scene 1: [夜] [室内] [旧地点] - 旧任务"],
                        },
                    ],
                    "scenes": [{"episode": 1, "title": "旧剧本", "scenes": [{"scene_number": 1}]}],
                },
            )

            response = SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content='{"title":"新标题","summary":"新摘要","beats":["新节拍1","新节拍2"],"scene_list":["Scene 1: [夜] [室内] [新地点] - 新任务"]}'
                        )
                    )
                ],
                usage=None,
            )
            fake_create = AsyncMock(return_value=response)
            fake_client = SimpleNamespace(
                chat=SimpleNamespace(
                    completions=SimpleNamespace(create=fake_create)
                )
            )

            with patch("app.services.story_llm._make_client", return_value=fake_client):
                result = await apply_chat(
                    "story-apply-chat-episode",
                    "episode",
                    chat_history=[
                        SimpleNamespace(role="user", text="把这一集改成更强的反转"),
                        SimpleNamespace(role="ai", text="当前剧情修改：增加反转\n后续影响：推进主线"),
                    ],
                    current_item={
                        "episode": 1,
                        "title": "旧标题",
                        "summary": "旧摘要",
                    },
                    db=session,
                    api_key="fake-key",
                )

            prompt = fake_create.await_args.kwargs["messages"][0]["content"]
            story = await repo.get_story(session, "story-apply-chat-episode")
            episode = story["outline"][0]

        self.assertIn('"beats": ["旧节拍1", "旧节拍2"]', prompt)
        self.assertIn('"scene_list": ["Scene 1: [夜] [室内] [旧地点] - 旧任务"]', prompt)
        self.assertEqual(
            episode,
            {
                "episode": 1,
                "title": "新标题",
                "summary": "新摘要",
                "beats": ["新节拍1", "新节拍2"],
                "scene_list": ["Scene 1: [夜] [室内] [新地点] - 新任务"],
            },
        )
        self.assertEqual(story["scenes"], [])
        self.assertEqual(result, episode)

    async def test_refine_character_keeps_existing_name_and_role(self):
        async with self.session_factory() as session:
            await repo.save_story(
                session,
                "story-refine-character-identity",
                {
                    "idea": "test",
                    "characters": [
                        {
                            "id": "char_hero",
                            "name": "林晓雨",
                            "role": "女主角",
                            "description": "原始描述",
                        },
                    ],
                    "scenes": [{"episode": 1, "title": "旧剧本", "scenes": [{"scene_number": 1}]}],
                },
            )

            response = SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content='{"characters":[{"id":"char_hero","name":"错误改名","role":"女配角","description":"更强势、更有压迫感"}],"relationships":null,"outline":null,"meta_theme":null}'
                        )
                    )
                ],
                usage=None,
            )
            fake_client = SimpleNamespace(
                chat=SimpleNamespace(
                    completions=SimpleNamespace(create=AsyncMock(return_value=response))
                )
            )

            with patch("app.services.story_llm._make_client", return_value=fake_client):
                result = await refine(
                    "story-refine-character-identity",
                    "character",
                    "角色描述增强",
                    db=session,
                    api_key="fake-key",
                )

            story = await repo.get_story(session, "story-refine-character-identity")
            character = story["characters"][0]

        self.assertEqual(character["name"], "林晓雨")
        self.assertEqual(character["role"], "女主角")
        self.assertEqual(character["description"], "更强势、更有压迫感")
        self.assertEqual(story["scenes"], [])
        self.assertEqual(result["characters"][0]["name"], "林晓雨")
        self.assertEqual(result["characters"][0]["role"], "女主角")

    async def test_generate_outline_clears_stale_scenes(self):
        async with self.session_factory() as session:
            await repo.save_story(
                session,
                "story-outline-clears-scenes",
                {
                    "idea": "test",
                    "scenes": [{"episode": 1, "title": "旧剧本", "scenes": [{"scene_number": 1}]}],
                },
            )

            result = await generate_outline(
                "story-outline-clears-scenes",
                selected_setting="新的世界观设定",
                db=session,
                api_key="",
            )
            story = await repo.get_story(session, "story-outline-clears-scenes")

        self.assertEqual(result["story_id"], "story-outline-clears-scenes")
        self.assertEqual(story["scenes"], [])

    async def test_generate_outline_preserves_character_aliases_from_blueprint(self):
        blueprint_response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            '{"meta":{"title":"雨夜茶馆","genre":"古风","episodes":6,"theme":"命运相逢","logline":"李明雨夜送信时被迫卷入茶馆旧案","visual_tone":"克制冷雨与暖灯对照"},'
                            '"characters":[{"name":"Boss Zhao","role":"support","description":"middle-aged shopkeeper, moustache, brown robe","aliases":["赵掌柜"]}],'
                            '"relationships":[{"source":"Boss Zhao","target":"Li Ming","label":"guarded alliance"}],'
                            '"season_plan":{"episode_arcs":['
                            '{"episode":1,"arc":"雨夜送信建立人物与旧案钩子"},'
                            '{"episode":2,"arc":"李明追查线索发现茶馆暗面"},'
                            '{"episode":3,"arc":"赵掌柜被迫暴露更深秘密"},'
                            '{"episode":4,"arc":"旧案真相逼近并反噬两人"},'
                            '{"episode":5,"arc":"双方联手对抗幕后势力"},'
                            '{"episode":6,"arc":"真相落定并完成关系收束"}'
                            '],"location_glossary":["江南茶馆","后院"],"tone_rules":["克制","雨夜氛围"]}}'
                        )
                    )
                )
            ],
            usage=None,
        )
        batch_response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            '{"outline":['
                            '{"episode":1,"title":"雨夜送信","summary":"李明雨夜抵达茶馆送信，卷入旧案开端。","beats":["送信到来","旧案钩子浮现"],"scene_list":["Scene 1: [夜] [室内] [江南茶馆] - 李明送信并发现异常。"]},'
                            '{"episode":2,"title":"追查线索","summary":"李明顺着细节追查茶馆暗面。","beats":["怀疑升级","发现新线索"],"scene_list":["Scene 1: [夜] [室内] [江南茶馆] - 李明试探赵掌柜。"]},'
                            '{"episode":3,"title":"秘密松动","summary":"赵掌柜被迫透露部分旧案真相。","beats":["互相试探","秘密松动"],"scene_list":["Scene 1: [夜] [室内] [后院] - 赵掌柜吐露旧事。"]},'
                            '{"episode":4,"title":"真相逼近","summary":"旧案反噬，两人陷入更大危机。","beats":["危机逼近","关系受压"],"scene_list":["Scene 1: [夜] [室外] [后巷] - 两人遭遇阻截。"]},'
                            '{"episode":5,"title":"并肩反击","summary":"李明与赵掌柜正式联手反击幕后势力。","beats":["达成同盟","主动出击"],"scene_list":["Scene 1: [夜] [室内] [江南茶馆] - 两人制定计划。"]},'
                            '{"episode":6,"title":"雨停灯明","summary":"真相落定，两人完成关系收束。","beats":["揭开真相","关系落定"],"scene_list":["Scene 1: [清晨] [室内] [江南茶馆] - 风波结束后的对话。"]}'
                            ']}'
                        )
                    )
                )
            ],
            usage=None,
        )

        async def fake_create(*, model, messages):
            prompt = messages[0]["content"]
            if "全局蓝图（blueprint）" in prompt:
                return blueprint_response
            if "本次只允许生成这些集数：1, 2, 3, 4, 5, 6" in prompt:
                return batch_response
            raise AssertionError(f"Unexpected prompt: {prompt}")

        fake_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=AsyncMock(side_effect=fake_create))
            )
        )

        async with self.session_factory() as session:
            await repo.save_story(
                session,
                "story-outline-aliases",
                {"idea": "test"},
            )

            with (
                patch("app.services.story_llm._make_client", return_value=fake_client),
                patch("app.services.story_llm.settings.outline_generation_concurrency", 1),
            ):
                result = await generate_outline(
                    "story-outline-aliases",
                    selected_setting="新的世界观设定",
                    db=session,
                    api_key="fake-key",
                    provider="openai",
                    model="gpt-test",
                )

            story = await repo.get_story(session, "story-outline-aliases")

        self.assertEqual(result["characters"][0]["aliases"], ["赵掌柜"])
        self.assertEqual(story["characters"][0]["aliases"], ["赵掌柜"])


if __name__ == "__main__":
    unittest.main()
