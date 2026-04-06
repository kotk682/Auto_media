import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException

from app.services.llm.openai import OpenAIProvider
from app.services.llm.qwen import QwenProvider
from app.services.llm.telemetry import LLMCallTracker
from app.services.story_llm import analyze_idea, generate_outline
from app.services.storyboard import parse_script_to_storyboard


class LLMTelemetryTrackerTests(unittest.TestCase):
    def test_tracker_promotes_slow_success_call_to_warning(self):
        with patch("app.services.llm.telemetry.settings.llm_telemetry_enabled", True):
            with patch("app.services.llm.telemetry.settings.llm_slow_log_threshold_ms", 100):
                with patch("app.services.llm.telemetry.time.perf_counter", side_effect=[1.0, 1.05, 1.25]):
                    with patch("app.services.llm.telemetry.logger.info") as info_mock:
                        with patch("app.services.llm.telemetry.logger.warning") as warning_mock:
                            tracker = LLMCallTracker(
                                provider="claude",
                                model="claude-sonnet-4-6",
                                request_chars=42,
                                context={"operation": "storyboard.parse", "story_id": "story-1"},
                            )
                            tracker.mark_first_token()
                            tracker.record_success(
                                usage={"prompt_tokens": 12, "completion_tokens": 34},
                                response_text="hello world",
                            )

        self.assertEqual(info_mock.call_count, 0)
        self.assertEqual(warning_mock.call_count, 2)
        success_fields = warning_mock.call_args_list[0].args[1]
        slow_fields = warning_mock.call_args_list[1].args[1]
        self.assertIn('operation="storyboard.parse"', success_fields)
        self.assertIn("first_token_ms=50", success_fields)
        self.assertIn("latency_ms=250", success_fields)
        self.assertIn("prompt_tokens=12", success_fields)
        self.assertIn('story_id="story-1"', success_fields)
        self.assertIn("LLM_CALL", warning_mock.call_args_list[0].args[0])
        self.assertIn("LLM_SLOW", warning_mock.call_args_list[1].args[0])
        self.assertIn("threshold_ms=100", slow_fields)

    def test_tracker_logs_non_slow_success_at_info(self):
        with patch("app.services.llm.telemetry.settings.llm_telemetry_enabled", True):
            with patch("app.services.llm.telemetry.settings.llm_slow_log_threshold_ms", 500):
                with patch("app.services.llm.telemetry.time.perf_counter", side_effect=[1.0, 1.08]):
                    with patch("app.services.llm.telemetry.logger.info") as info_mock:
                        with patch("app.services.llm.telemetry.logger.warning") as warning_mock:
                            tracker = LLMCallTracker(
                                provider="claude",
                                model="claude-sonnet-4-6",
                                request_chars=42,
                                context={"operation": "storyboard.parse", "story_id": "story-1"},
                            )
                            tracker.record_success(
                                usage={"prompt_tokens": 12, "completion_tokens": 34},
                                response_text="hello world",
                            )

        self.assertEqual(info_mock.call_count, 1)
        self.assertEqual(warning_mock.call_count, 0)
        success_fields = info_mock.call_args.args[1]
        self.assertIn('operation="storyboard.parse"', success_fields)
        self.assertIn("latency_ms=80", success_fields)
        self.assertIn("success=true", success_fields)

    def test_tracker_logs_cache_metrics_when_present(self):
        with patch("app.services.llm.telemetry.settings.llm_telemetry_enabled", True):
            with patch("app.services.llm.telemetry.settings.llm_slow_log_threshold_ms", 500):
                with patch("app.services.llm.telemetry.time.perf_counter", side_effect=[1.0, 1.08]):
                    with patch("app.services.llm.telemetry.logger.info") as info_mock:
                        tracker = LLMCallTracker(
                            provider="openai",
                            model="gpt-4o",
                            request_chars=42,
                            context={"operation": "storyboard.parse"},
                        )
                        tracker.record_success(
                            usage={
                                "prompt_tokens": 1000,
                                "completion_tokens": 50,
                                "cache_enabled": True,
                                "cached_tokens": 800,
                                "cache_creation_input_tokens": 0,
                            },
                            response_text="hello world",
                        )

        success_fields = info_mock.call_args.args[1]
        self.assertIn("cache_enabled=true", success_fields)
        self.assertIn("cached_tokens=800", success_fields)
        self.assertIn("uncached_prompt_tokens=200", success_fields)
        self.assertIn("cache_hit_ratio=0.8", success_fields)

    def test_tracker_logs_failure_context(self):
        with patch("app.services.llm.telemetry.settings.llm_telemetry_enabled", True):
            with patch("app.services.llm.telemetry.time.perf_counter", side_effect=[2.0, 2.3]):
                with patch("app.services.llm.telemetry.logger.warning") as warning_mock:
                    tracker = LLMCallTracker(
                        provider="openai",
                        model="gpt-4o-mini",
                        request_chars=18,
                        context={"operation": "story.chat", "story_id": "story-2", "mode": "generic"},
                    )
                    tracker.record_failure(RuntimeError("boom"))

        self.assertEqual(warning_mock.call_count, 1)
        failure_fields = warning_mock.call_args.args[1]
        self.assertIn("success=false", failure_fields)
        self.assertIn('error_type="RuntimeError"', failure_fields)
        self.assertIn('mode="generic"', failure_fields)


class StoryboardTelemetryContextTests(unittest.IsolatedAsyncioTestCase):
    async def test_parse_script_to_storyboard_passes_business_context_to_provider(self):
        raw_response = json.dumps(
            [
                {
                    "shot_id": "scene1_shot1",
                    "estimated_duration": 4,
                    "scene_intensity": "low",
                    "storyboard_description": "雨夜里，主角停在茶馆门口。",
                    "camera_setup": {
                        "shot_size": "MS",
                        "camera_angle": "Eye-level",
                        "movement": "Static",
                    },
                    "visual_elements": {
                        "subject_and_clothing": "young scholar in dark robe",
                        "action_and_expression": "pauses at the doorway, alert expression",
                        "environment_and_props": "teahouse doorway, paper lantern, wet stone steps",
                        "lighting_and_color": "cool rainy blue with warm lantern glow",
                    },
                    "final_video_prompt": (
                        "Medium shot. Static camera. A young scholar pauses at the teahouse doorway in rain."
                    ),
                }
            ],
            ensure_ascii=False,
        )
        provider = SimpleNamespace(
            complete_messages_with_usage=AsyncMock(
                return_value=(raw_response, {"prompt_tokens": 10, "completion_tokens": 5})
            )
        )

        with patch("app.services.storyboard.get_llm_provider", return_value=provider):
            shots, usage = await parse_script_to_storyboard(
                "# 第1集 雨夜来客\n## 场景1\n【环境】茶馆门口\n【画面】李明停在门口。",
                provider="claude",
                telemetry_context={"story_id": "story-1", "pipeline_id": "pipe-1"},
            )

        self.assertEqual(len(shots), 1)
        self.assertEqual(usage["prompt_tokens"], 10)
        kwargs = provider.complete_messages_with_usage.await_args.kwargs
        self.assertEqual(
            kwargs["telemetry_context"],
            {
                "operation": "storyboard.parse",
                "story_id": "story-1",
                "pipeline_id": "pipe-1",
            },
        )


class ProviderPromptCacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_openai_provider_uses_prompt_cache_key_and_returns_cached_tokens(self):
        provider = OpenAIProvider(api_key="test-key", model="gpt-4o")
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
            usage=SimpleNamespace(
                prompt_tokens=1800,
                completion_tokens=12,
                prompt_tokens_details=SimpleNamespace(cached_tokens=1400),
            ),
        )
        provider._client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=AsyncMock(return_value=response))
            )
        )

        _, usage = await provider.complete_messages_with_usage(
            system="system" * 400,
            messages=[
                {"role": "user", "content": "stable prefix " * 300, "cacheable": True},
                {"role": "user", "content": "dynamic suffix"},
            ],
            enable_caching=True,
            telemetry_context={"operation": "storyboard.parse"},
        )

        kwargs = provider._client.chat.completions.create.await_args.kwargs
        self.assertIn("prompt_cache_key", kwargs["extra_body"])
        self.assertTrue(usage["cache_enabled"])
        self.assertEqual(usage["cached_tokens"], 1400)

    async def test_openai_provider_does_not_report_cache_enabled_when_request_has_no_prompt_cache_key(self):
        provider = OpenAIProvider(
            api_key="test-key",
            model="gpt-4o",
            base_url="https://example-proxy.invalid/v1",
        )
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
            usage=SimpleNamespace(
                prompt_tokens=1800,
                completion_tokens=12,
                prompt_tokens_details=SimpleNamespace(cached_tokens=0),
            ),
        )
        provider._client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=AsyncMock(return_value=response))
            )
        )

        _, usage = await provider.complete_messages_with_usage(
            system="system" * 400,
            messages=[
                {"role": "user", "content": "stable prefix " * 300, "cacheable": True},
                {"role": "user", "content": "dynamic suffix"},
            ],
            enable_caching=True,
            telemetry_context={"operation": "storyboard.parse"},
        )

        kwargs = provider._client.chat.completions.create.await_args.kwargs
        self.assertIsNone(kwargs["extra_body"])
        self.assertNotIn("cache_enabled", usage)

    async def test_qwen_provider_marks_cacheable_message_blocks_and_surfaces_cache_usage(self):
        provider = QwenProvider(api_key="test-key", model="qwen-plus")

        async def stream():
            yield SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content="hello"))],
                usage=None,
            )
            yield SimpleNamespace(
                choices=[],
                usage=SimpleNamespace(
                    prompt_tokens=1700,
                    completion_tokens=15,
                    prompt_tokens_details=SimpleNamespace(
                        cached_tokens=1200,
                        cache_creation_input_tokens=100,
                    ),
                ),
            )

        provider._client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=AsyncMock(return_value=stream()))
            )
        )

        _, usage = await provider.complete_messages_with_usage(
            system="system" * 400,
            messages=[
                {"role": "user", "content": "stable prefix " * 300, "cacheable": True},
                {"role": "user", "content": "dynamic suffix"},
            ],
            enable_caching=True,
            telemetry_context={"operation": "storyboard.parse"},
        )

        request_messages = provider._client.chat.completions.create.await_args.kwargs["messages"]
        cacheable_content = request_messages[1]["content"]
        self.assertIsInstance(cacheable_content, list)
        self.assertEqual(cacheable_content[0]["cache_control"], {"type": "ephemeral"})
        self.assertTrue(usage["cache_enabled"])
        self.assertEqual(usage["cached_tokens"], 1200)
        self.assertEqual(usage["cache_creation_input_tokens"], 100)

    async def test_qwen_provider_does_not_report_cache_enabled_for_non_dashscope_endpoint(self):
        provider = QwenProvider(
            api_key="test-key",
            model="qwen-plus",
            base_url="https://example-proxy.invalid/v1",
        )

        async def stream():
            yield SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content="hello"))],
                usage=None,
            )
            yield SimpleNamespace(
                choices=[],
                usage=SimpleNamespace(
                    prompt_tokens=1700,
                    completion_tokens=15,
                    prompt_tokens_details=SimpleNamespace(
                        cached_tokens=0,
                        cache_creation_input_tokens=0,
                    ),
                ),
            )

        provider._client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=AsyncMock(return_value=stream()))
            )
        )

        _, usage = await provider.complete_messages_with_usage(
            system="system" * 400,
            messages=[
                {"role": "user", "content": "stable prefix " * 300, "cacheable": True},
                {"role": "user", "content": "dynamic suffix"},
            ],
            enable_caching=True,
            telemetry_context={"operation": "storyboard.parse"},
        )

        request_messages = provider._client.chat.completions.create.await_args.kwargs["messages"]
        self.assertIsInstance(request_messages[1]["content"], str)
        self.assertNotIn("cache_enabled", usage)


class StoryLlmTelemetryIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_analyze_idea_uses_tracker_for_direct_openai_chain(self):
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"analysis":"分析","suggestions":["建议"],"placeholder":"占位提示"}'
                    )
                )
            ],
            usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7),
        )
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=AsyncMock(return_value=response))
            )
        )
        tracker = SimpleNamespace(record_failure=Mock(), record_success=Mock())

        with patch("app.services.story_llm._make_client", return_value=fake_client):
            with patch("app.services.story_llm._build_llm_tracker", return_value=tracker) as tracker_builder:
                with patch("app.services.story_llm.repo.save_story", new=AsyncMock()):
                    result = await analyze_idea(
                        "雨夜古镇",
                        "古风",
                        "克制",
                        db=object(),
                        api_key="fake-key",
                        provider="openai",
                    )

        tracker_builder.assert_called_once()
        tracker.record_failure.assert_not_called()
        tracker.record_success.assert_called_once()
        self.assertEqual(result["usage"], {"prompt_tokens": 11, "completion_tokens": 7})

    async def test_analyze_idea_records_failure_when_persistence_fails_after_llm_response(self):
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"analysis":"分析","suggestions":["建议"],"placeholder":"占位提示"}'
                    )
                )
            ],
            usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7),
        )
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=AsyncMock(return_value=response))
            )
        )
        tracker = SimpleNamespace(record_failure=Mock(), record_success=Mock())

        with patch("app.services.story_llm._make_client", return_value=fake_client):
            with patch("app.services.story_llm._build_llm_tracker", return_value=tracker):
                with patch("app.services.story_llm.repo.save_story", new=AsyncMock(side_effect=RuntimeError("db down"))):
                    with self.assertRaises(RuntimeError):
                        await analyze_idea(
                            "雨夜古镇",
                            "古风",
                            "克制",
                            db=object(),
                            api_key="fake-key",
                            provider="openai",
                        )

        tracker.record_success.assert_not_called()
        tracker.record_failure.assert_called_once()

    async def test_generate_outline_records_failure_when_outline_validation_fails(self):
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
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
        )
        invalid_batch_response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"outline":[{"episode":1,"title":"第一集","summary":"摘要","beats":["Beat 1"],"scene_list":["Scene 1"]}]}'
                    )
                )
            ],
            usage=SimpleNamespace(prompt_tokens=9, completion_tokens=4),
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
            usage=SimpleNamespace(prompt_tokens=9, completion_tokens=4),
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
        trackers = []

        def build_tracker(*args, **kwargs):
            tracker = SimpleNamespace(record_failure=Mock(), record_success=Mock(), mark_first_token=Mock())
            trackers.append((kwargs["operation"], tracker))
            return tracker

        with patch("app.services.story_llm._make_client", return_value=fake_client):
            with patch("app.services.story_llm.settings.outline_generation_concurrency", 2):
                with patch("app.services.story_llm._build_llm_tracker", side_effect=build_tracker):
                    with self.assertRaises(HTTPException):
                        await generate_outline(
                            "story-invalid-outline",
                            selected_setting="新的世界观设定",
                            db=object(),
                            api_key="fake-key",
                            provider="qwen",
                            model="qwen-max",
                        )

        self.assertTrue(any(operation == "story.generate_outline.blueprint" for operation, _ in trackers))
        self.assertTrue(any(operation == "story.generate_outline.batch" for operation, _ in trackers))
        self.assertEqual(
            sum(1 for _, tracker in trackers if tracker.record_failure.called),
            1,
        )
