import json
import unittest
from pathlib import Path

class MediaRegistryAndSovereigntyTests(unittest.TestCase):
    def test_open_video_backends_are_registered(self):
        data=json.loads(Path('media/open_video_backend_registry.json').read_text())
        ids={x['id'] for x in data['backends']}
        self.assertTrue({'ltx-2','wan-2.2','hunyuanvideo-1.5','cogvideox'} <= ids)

    def test_customer_owns_reserved_projects(self):
        data=json.loads(Path('projects/project_sovereignty.json').read_text())
        for key in ('GOLDEN_WALLET','BEAST'):
            self.assertEqual(data['projects'][key]['owner'],'customer')
            self.assertEqual(data['projects'][key]['ai_ownership'],'none')

if __name__=='__main__':
    unittest.main()