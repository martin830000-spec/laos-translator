import unittest
from preflight import validate_metadata
class Preflight(unittest.TestCase):
 def test_supported_and_error_on_minimal38(self):
  m=dict(name='models/gemini-3.8-flash',supportedGenerationMethods=['generateContent'],outputTokenLimit=65536)
  self.assertTrue(validate_metadata('gemini-3.8-flash','low',1024,m))
  with self.assertRaises(ValueError):validate_metadata('gemini-3.8-flash','minimal',1024,m)
 def test_alias_missing_method_and_cap_fail_closed(self):
  for meta in [dict(name='models/gemini-3.6-flash',supportedGenerationMethods=['generateContent'],outputTokenLimit=65536),dict(name='models/gemini-3.5-flash-lite',supportedGenerationMethods=[],outputTokenLimit=65536),dict(name='models/gemini-3.5-flash-lite',supportedGenerationMethods=['generateContent'],outputTokenLimit=100)]:
   with self.assertRaises(ValueError):validate_metadata('gemini-3.5-flash-lite','minimal',1024,meta)
