import unittest
from intelligence.trait_genome import IntelligenceProfile, TraitEvidence, TraitGenome
from knowledge.lawbook import LawBook
from language.vxsl import VXSLCompiler

class LawTraitLanguageTests(unittest.TestCase):
    def test_lawbook_requires_validation_state(self):
        book = LawBook()
        law = book.ingest('physics', 'Newton law', 'F=m*a', 'user-approved-source', ['chat-output:authorized'], ['symbolic-checker'])
        self.assertEqual(book.get(law.id).status, 'unverified')
        self.assertEqual(book.validate(law.id, 'symbolic-checker', True).status, 'verified')

    def test_trait_genome_composes_mission_mind(self):
        genome = TraitGenome()
        genome.register(IntelligenceProfile('model-a','local','open-model-a',(TraitEvidence('math',.9,'bench-1','ev-1'),TraitEvidence('reasoning',.9,'bench-2','ev-2'))))
        genome.register(IntelligenceProfile('model-b','local','open-model-b',(TraitEvidence('math',.4,'bench-1','ev-3'),TraitEvidence('reasoning',.95,'bench-2','ev-4'))))
        composed = genome.compose_mind('mathematical-mind',['math','reasoning'],.8)
        self.assertEqual([x['profile_id'] for x in composed['model_candidates']], ['model-a'])

    def test_vxsl_preserves_domains_and_project(self):
        source = 'system Demo {\n project BEAST\n domain mathematics\n domain physics\n domain engineering\n domain computing\n quantity mass: kg\n law F = m*a\n constraint deterministic_replay\n }'
        ir = VXSLCompiler().compile(source)
        self.assertEqual(ir['project_id'], 'BEAST')
        self.assertEqual(len(ir['domains']), 4)
        self.assertIn('Modelica', ir['compiler']['targets'])

if __name__ == '__main__':
    unittest.main()
