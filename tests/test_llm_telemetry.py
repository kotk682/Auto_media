import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException

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
        async def fake_stream():
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content='{"meta":{"episodes":6},"outline":[{"episode":1,"title":"第一集","summary":"摘要","beats":["Beat 1"],"scene_list":["Scene 1"]}]}'
                        )
                    )
                ]
            )

        fake_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=AsyncMock(return_value=fake_stream()))
            )
        )
        tracker = SimpleNamespace(record_failure=Mock(), record_success=Mock(), mark_first_token=Mock())

        with patch("app.services.story_llm._make_client", return_value=fake_client):
            with patch("app.services.story_llm._build_llm_tracker", return_value=tracker):
                with self.assertRaises(HTTPException):
                    await generate_outline(
                        "story-invalid-outline",
                        selected_setting="新的世界观设定",
                        db=object(),
                        api_key="fake-key",
                        provider="qwen",
                        model="qwen-max",
                    )

        tracker.record_success.assert_not_called()
        tracker.record_failure.assert_called_once()
