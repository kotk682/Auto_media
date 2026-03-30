import unittest

from app.services.storyboard_state import build_storyboard_generation_state


class StoryboardStateTests(unittest.TestCase):
    def test_partial_shot_merge_preserves_existing_fields_and_filters_transient_keys(self):
        story = {
            "meta": {
                "storyboard_generation": {
                    "shots": [
                        {
                            "shot_id": "shot-1",
                            "storyboard_description": "old description",
                            "image_url": "/media/images/shot-1-old.png",
                        },
                        {
                            "shot_id": "shot-2",
                            "storyboard_description": "second shot",
                        },
                    ]
                }
            }
        }

        state = build_storyboard_generation_state(
            story,
            shots=[
                {
                    "shot_id": "shot-1",
                    "storyboard_description": "new description",
                    "ttsLoading": True,
                    "imageLoading": True,
                    "videoLoading": True,
                }
            ],
            partial_shots=True,
        )

        self.assertEqual([shot["shot_id"] for shot in state["shots"]], ["shot-1", "shot-2"])
        self.assertEqual(state["shots"][0]["storyboard_description"], "new description")
        self.assertEqual(state["shots"][0]["image_url"], "/media/images/shot-1-old.png")
        self.assertNotIn("ttsLoading", state["shots"][0])
        self.assertNotIn("imageLoading", state["shots"][0])
        self.assertNotIn("videoLoading", state["shots"][0])

    def test_generated_files_are_applied_back_to_shots_and_append_new_entries(self):
        story = {
            "meta": {
                "storyboard_generation": {
                    "shots": [
                        {
                            "shot_id": "shot-1",
                            "storyboard_description": "opening shot",
                        }
                    ]
                }
            }
        }

        state = build_storyboard_generation_state(
            story,
            generated_files={
                "tts": {
                    "shot-1": {
                        "shot_id": "shot-1",
                        "audio_url": "/media/audio/shot-1.mp3",
                        "duration_seconds": 1.75,
                    }
                },
                "images": {
                    "shot-1": {
                        "shot_id": "shot-1",
                        "image_url": "/media/images/shot-1.png",
                        "image_path": "media/images/shot-1.png",
                    },
                    "shot-2": {
                        "shot_id": "shot-2",
                        "image_url": "/media/images/shot-2.png",
                        "image_path": "media/images/shot-2.png",
                    },
                },
                "videos": {
                    "shot-1": {
                        "shot_id": "shot-1",
                        "video_url": "/media/videos/shot-1.mp4",
                        "video_path": "media/videos/shot-1.mp4",
                    }
                },
            },
        )

        self.assertEqual([shot["shot_id"] for shot in state["shots"]], ["shot-1", "shot-2"])
        self.assertEqual(state["shots"][0]["audio_url"], "/media/audio/shot-1.mp3")
        self.assertEqual(state["shots"][0]["audio_duration"], 1.75)
        self.assertEqual(state["shots"][0]["image_url"], "/media/images/shot-1.png")
        self.assertNotIn("last_frame_url", state["shots"][0])
        self.assertEqual(state["shots"][0]["video_url"], "/media/videos/shot-1.mp4")
        self.assertEqual(state["shots"][1]["image_url"], "/media/images/shot-2.png")

    def test_context_usage_and_final_video_are_updated(self):
        story = {
            "meta": {
                "storyboard_generation": {
                    "pipeline_id": "pipeline-old",
                    "project_id": "project-old",
                    "story_id": "story-old",
                    "final_video_url": "/media/videos/old.mp4",
                }
            }
        }

        state = build_storyboard_generation_state(
            story,
            pipeline_id="pipeline-new",
            project_id="project-new",
            story_id="story-new",
            final_video_url="/media/videos/final.mp4",
            usage={"prompt_tokens": 12, "completion_tokens": 34},
        )

        self.assertEqual(state["pipeline_id"], "pipeline-new")
        self.assertEqual(state["project_id"], "project-new")
        self.assertEqual(state["story_id"], "story-new")
        self.assertEqual(state["final_video_url"], "/media/videos/final.mp4")
        self.assertEqual(state["usage"], {"prompt_tokens": 12, "completion_tokens": 34})
        self.assertTrue(state["updated_at"])

    def test_transition_generated_files_and_timeline_are_persisted(self):
        story = {
            "meta": {
                "storyboard_generation": {
                    "generated_files": {
                        "transitions": {
                            "transition_shot-1__shot-2": {
                                "transition_id": "transition_shot-1__shot-2",
                                "video_url": "/media/videos/transition-old.mp4",
                            }
                        }
                    }
                }
            }
        }

        state = build_storyboard_generation_state(
            story,
            generated_files={
                "transitions": {
                    "transition_shot-2__shot-3": {
                        "transition_id": "transition_shot-2__shot-3",
                        "video_url": "/media/videos/transition-new.mp4",
                    }
                },
                "timeline": [
                    {"item_type": "shot", "item_id": "shot-1"},
                    {"item_type": "transition", "item_id": "transition_shot-1__shot-2"},
                    {"item_type": "shot", "item_id": "shot-2"},
                ],
            },
        )

        self.assertIn("transition_shot-1__shot-2", state["generated_files"]["transitions"])
        self.assertIn("transition_shot-2__shot-3", state["generated_files"]["transitions"])
        self.assertEqual(state["generated_files"]["timeline"][1]["item_type"], "transition")

    def test_full_storyboard_refresh_replaces_stale_generated_files_and_clears_final_video(self):
        story = {
            "meta": {
                "storyboard_generation": {
                    "shots": [
                        {"shot_id": "shot-old", "video_url": "/media/videos/shot-old.mp4"},
                    ],
                    "generated_files": {
                        "videos": {
                            "shot-old": {
                                "shot_id": "shot-old",
                                "video_url": "/media/videos/shot-old.mp4",
                            }
                        },
                        "transitions": {
                            "transition_shot-old__shot-2": {
                                "transition_id": "transition_shot-old__shot-2",
                                "video_url": "/media/videos/transition-old.mp4",
                            }
                        },
                        "final_video_url": "/media/videos/final-old.mp4",
                    },
                    "final_video_url": "/media/videos/final-old.mp4",
                }
            }
        }

        state = build_storyboard_generation_state(
            story,
            shots=[
                {"shot_id": "shot-1", "storyboard_description": "new opening"},
                {"shot_id": "shot-2", "storyboard_description": "new follow-up"},
            ],
            generated_files={
                "storyboard": {
                    "shots": [
                        {"shot_id": "shot-1", "storyboard_description": "new opening"},
                        {"shot_id": "shot-2", "storyboard_description": "new follow-up"},
                    ]
                }
            },
            replace_generated_files=True,
            prune_generated_files_to_shots=True,
            clear_final_video=True,
        )

        self.assertEqual([shot["shot_id"] for shot in state["shots"]], ["shot-1", "shot-2"])
        self.assertEqual(list(state["generated_files"].keys()), ["storyboard"])
        self.assertEqual(state["final_video_url"], "")

    def test_regenerated_image_invalidates_dependent_videos_transitions_and_final_video(self):
        story = {
            "meta": {
                "storyboard_generation": {
                    "shots": [
                        {"shot_id": "shot-1", "image_url": "/media/images/shot-1-old.png", "video_url": "/media/videos/shot-1.mp4"},
                        {"shot_id": "shot-2", "image_url": "/media/images/shot-2.png", "video_url": "/media/videos/shot-2.mp4"},
                    ],
                    "generated_files": {
                        "images": {
                            "shot-1": {"shot_id": "shot-1", "image_url": "/media/images/shot-1-old.png"},
                            "shot-2": {"shot_id": "shot-2", "image_url": "/media/images/shot-2.png"},
                        },
                        "videos": {
                            "shot-1": {"shot_id": "shot-1", "video_url": "/media/videos/shot-1.mp4"},
                            "shot-2": {"shot_id": "shot-2", "video_url": "/media/videos/shot-2.mp4"},
                        },
                        "transitions": {
                            "transition_shot-1__shot-2": {
                                "transition_id": "transition_shot-1__shot-2",
                                "from_shot_id": "shot-1",
                                "to_shot_id": "shot-2",
                                "video_url": "/media/videos/transition-shot-1__shot-2.mp4",
                            }
                        },
                        "timeline": [
                            {"item_type": "shot", "item_id": "shot-1"},
                            {"item_type": "transition", "item_id": "transition_shot-1__shot-2"},
                            {"item_type": "shot", "item_id": "shot-2"},
                        ],
                    },
                    "final_video_url": "/media/videos/final-old.mp4",
                }
            }
        }

        state = build_storyboard_generation_state(
            story,
            shots=[{"shot_id": "shot-1"}],
            partial_shots=True,
            generated_files={
                "images": {
                    "shot-1": {"shot_id": "shot-1", "image_url": "/media/images/shot-1-new.png"},
                }
            },
            prune_generated_files_to_shots=True,
            invalidate_shot_ids=["shot-1"],
            clear_videos_for_invalidated_shots=True,
            clear_final_video=True,
        )

        self.assertEqual(state["shots"][0]["image_url"], "/media/images/shot-1-new.png")
        self.assertNotIn("video_url", state["shots"][0])
        self.assertEqual(state["shots"][1]["video_url"], "/media/videos/shot-2.mp4")
        self.assertEqual(state["generated_files"]["videos"], {"shot-2": {"shot_id": "shot-2", "video_url": "/media/videos/shot-2.mp4"}})
        self.assertEqual(state["generated_files"]["transitions"], {})
        self.assertEqual(state["generated_files"]["timeline"], [{"item_type": "shot", "item_id": "shot-1"}, {"item_type": "shot", "item_id": "shot-2"}])
        self.assertEqual(state["final_video_url"], "")

    def test_invalidation_without_authoritative_shots_does_not_prune_unrelated_assets(self):
        story = {
            "meta": {
                "storyboard_generation": {
                    "shots": [],
                    "generated_files": {
                        "images": {
                            "shot-1": {"shot_id": "shot-1", "image_url": "/media/images/shot-1.png"},
                            "shot-2": {"shot_id": "shot-2", "image_url": "/media/images/shot-2.png"},
                        },
                        "videos": {
                            "shot-1": {"shot_id": "shot-1", "video_url": "/media/videos/shot-1.mp4"},
                            "shot-2": {"shot_id": "shot-2", "video_url": "/media/videos/shot-2.mp4"},
                        },
                        "transitions": {
                            "transition_shot-1__shot-2": {
                                "transition_id": "transition_shot-1__shot-2",
                                "from_shot_id": "shot-1",
                                "to_shot_id": "shot-2",
                                "video_url": "/media/videos/transition-shot-1__shot-2.mp4",
                            }
                        },
                        "timeline": [
                            {"item_type": "shot", "item_id": "shot-1"},
                            {"item_type": "transition", "item_id": "transition_shot-1__shot-2"},
                            {"item_type": "shot", "item_id": "shot-2"},
                        ],
                        "final_video_url": "/media/videos/final-old.mp4",
                    },
                    "final_video_url": "/media/videos/final-old.mp4",
                }
            }
        }

        state = build_storyboard_generation_state(
            story,
            invalidate_shot_ids=["shot-1"],
            clear_videos_for_invalidated_shots=True,
            clear_final_video=True,
        )

        self.assertEqual(
            state["generated_files"]["images"],
            {
                "shot-1": {"shot_id": "shot-1", "image_url": "/media/images/shot-1.png"},
                "shot-2": {"shot_id": "shot-2", "image_url": "/media/images/shot-2.png"},
            },
        )
        self.assertEqual(
            state["generated_files"]["videos"],
            {"shot-2": {"shot_id": "shot-2", "video_url": "/media/videos/shot-2.mp4"}},
        )
        self.assertEqual(state["generated_files"]["transitions"], {})
        self.assertEqual(
            state["generated_files"]["timeline"],
            [
                {"item_type": "shot", "item_id": "shot-1"},
                {"item_type": "shot", "item_id": "shot-2"},
            ],
        )
        self.assertEqual(state["final_video_url"], "")

    def test_replace_generated_files_clears_missing_media_fields_from_existing_shots(self):
        story = {
            "meta": {
                "storyboard_generation": {
                    "shots": [
                        {
                            "shot_id": "shot-1",
                            "audio_url": "/media/audio/shot-1.mp3",
                            "audio_duration": 1.8,
                            "image_url": "/media/images/shot-1.png",
                            "video_url": "/media/videos/shot-1.mp4",
                        }
                    ],
                    "generated_files": {
                        "tts": {
                            "shot-1": {
                                "shot_id": "shot-1",
                                "audio_url": "/media/audio/shot-1.mp3",
                                "duration_seconds": 1.8,
                            }
                        },
                        "images": {
                            "shot-1": {"shot_id": "shot-1", "image_url": "/media/images/shot-1.png"},
                        },
                        "videos": {
                            "shot-1": {"shot_id": "shot-1", "video_url": "/media/videos/shot-1.mp4"},
                        },
                    },
                }
            }
        }

        state = build_storyboard_generation_state(
            story,
            generated_files={
                "storyboard": {
                    "shots": [
                        {"shot_id": "shot-1", "storyboard_description": "refreshed shot"},
                    ]
                }
            },
            replace_generated_files=True,
        )

        self.assertEqual(list(state["generated_files"].keys()), ["storyboard"])
        self.assertNotIn("audio_url", state["shots"][0])
        self.assertNotIn("audio_duration", state["shots"][0])
        self.assertNotIn("image_url", state["shots"][0])
        self.assertNotIn("video_url", state["shots"][0])


if __name__ == "__main__":
    unittest.main()
