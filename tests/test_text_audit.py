import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import json

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/chinese-prose-quality/scripts/text_audit.py'
spec = importlib.util.spec_from_file_location('text_audit', SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

class CandidateTests(unittest.TestCase):
    def test_source_unchanged_and_no_semantic_pass_claim(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'draft.txt'
            original = '小河慢慢地向东流。'.encode()
            p.write_bytes(original)
            r = subprocess.run([sys.executable, str(SCRIPT), str(p)], capture_output=True, text=True, check=True)
            report = json.loads(r.stdout)
            self.assertEqual(p.read_bytes(), original)
            self.assertFalse(report['semantic_review_completed'])
            self.assertEqual(report['candidate_count'], 0)
    def test_candidates_have_localizable_evidence(self):
        s = '第一行。\n费用下降了一倍。约30人左右参加。'
        r = audit.scan(s)
        self.assertEqual({i['rule'] for i in r}, {'Q-REDUCE', 'Q-APPROX'})
        for i in r:
            self.assertEqual(i['line'], 2)
            self.assertEqual(s[i['offset']:i['offset'] + len(i['snippet'])], i['snippet'])
            self.assertEqual(i['status'], 'needs_context_review')
    def test_excludes_common_code_contexts(self):
        s = '```python\nx = "..."\n```\n`...`\nhttps://example.test/...\n正常正文。'
        self.assertEqual(audit.scan(s), [])
    def test_pairs_cross_lines_and_nested(self):
        self.assertEqual(audit.scan('她说：“请阅读《小溪》\n的第二章。”'), [])
    def test_non_error_antipatterns_not_auto_rejected(self):
        s = '为避免没有人接待，他安排了轮班。是否有效，取决于实施质量。平均分超过80分。'
        self.assertEqual(audit.scan(s), [])
    def test_typo_and_mismatch_are_only_candidates(self):
        r = audit.scan('他写下：“今天，，我们读《小溪”。')
        self.assertTrue(any(i['rule'] == 'P-DUP' for i in r))
        self.assertTrue(any(i['rule'] == 'P-PAIR' for i in r))
        self.assertTrue(all(i['status'] == 'needs_context_review' for i in r))

if __name__ == '__main__':
    unittest.main()
