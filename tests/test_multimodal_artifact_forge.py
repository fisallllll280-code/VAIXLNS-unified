import unittest
from media.multimodal_artifact_forge import MultimodalArtifactForge

class MultimodalArtifactForgeTests(unittest.TestCase):
    def test_one_system_produces_multiple_media_views(self):
        artifacts=MultimodalArtifactForge().build('sys:1',['mathematics','physics','engineering','computing'],['vxsl:1','sim:1'])
        kinds={a.kind for a in artifacts}
        self.assertTrue({'engineering-diagram','technical-storyboard','engineering-video','interactive-exploration','digital-twin-view'} <= kinds)
        self.assertEqual(artifacts[0].provenance,('vxsl:1','sim:1'))

if __name__=='__main__':
    unittest.main()