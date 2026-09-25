import json
import unittest
from media.backend_selector import VideoBackendSelector

class VideoAndModelRegistryTests(unittest.TestCase):
    def test_selector_is_requirement_driven(self):
        s=VideoBackendSelector()
        picks=s.select(['audio-to-video','synchronized-audio-video'])
        self.assertTrue(picks)
        self.assertEqual(picks[0]['id'],'ltx-2')

    def test_model_registry_contains_open_weight_families(self):
        data=json.loads(open('intelligence/open_model_registry.json',encoding='utf-8').read())
        ids={m['id'] for m in data['models']}
        self.assertTrue({'gpt-oss-120b','Qwen3','Kimi-K3'} <= ids)

if __name__=='__main__':
    unittest.main()