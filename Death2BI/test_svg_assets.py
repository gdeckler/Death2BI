import base64
import unittest
from presentation import enrich_report, safe_svg


class SvgAssetsTests(unittest.TestCase):
    def test_self_contained_svg_survives_and_active_content_is_removed(self):
        source = b'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1280" height="720" onload="bad()"><defs><clipPath id="clip"><rect width="10" height="10"/></clipPath></defs><image id="img" xlink:href="data:image/png;base64,YQ=="/><use xlink:href="#img" clip-path="url(#clip)"/><script>bad()</script><foreignObject><div>bad</div></foreignObject><image href="https://example.org/tracker"/><rect style="fill:url(https://example.org/a)"/><animate attributeName="href" to="javascript:bad()"/></svg>'''
        result = safe_svg(source)
        for bad in (b'onload', b'<script', b'foreignObject', b'example.org', b'javascript:'):
            self.assertNotIn(bad, result)
        self.assertIn(b'data:image/png;base64,YQ==', result)
        self.assertIn(b'url(#clip)', result)
        self.assertIn(b'#img', result)
        model = {'pages': []}
        enrich_report(model, {'Report/StaticResources/RegisteredResources/Background.SVG': source})
        asset = model['assets']['Background.SVG']
        self.assertTrue(asset.startswith('data:image/svg+xml;base64,'))
        self.assertEqual(base64.b64decode(asset.split(',')[1]), result)

    def test_safe_animation_styles_survive(self):
        good=b'<svg xmlns="http://www.w3.org/2000/svg"><style>.dark{opacity:0;animation:fade 10s infinite}@keyframes fade{0%{opacity:0}90%{opacity:.8}}@font-face{font-family:X;src:url(data:font/woff2;base64,YQ==)}</style><rect class="dark" width="10" height="10"/></svg>'
        result=safe_svg(good);self.assertIn(b'opacity:0',result);self.assertIn(b'@keyframes',result);self.assertIn(b'data:font/woff2',result)
        for css in ('@import "https://example.org/a";','.x{fill:url(https://example.org/a)}','.x{fill:url(\\68ttps://example.org/a)}'):
            bad=('<svg xmlns="http://www.w3.org/2000/svg"><style>'+css+'</style><rect/></svg>').encode()
            self.assertNotIn(b'<style',safe_svg(bad))

    def test_invalid_and_entity_documents_are_not_embedded(self):
        for source in (b'<html/>', b'<svg', b'<!DOCTYPE svg [<!ENTITY x "x">]><svg/>'):
            self.assertIsNone(safe_svg(source))


if __name__ == '__main__':
    unittest.main()
