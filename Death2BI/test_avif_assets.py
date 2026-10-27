"""Embedded AVIF artwork remains byte-for-byte intact, including alpha planes."""
import base64
import unittest

from presentation import enrich_report, safe_svg


# A two-pixel-wide AVIF with a separate alpha item, generated from RGBA pixels.
# Keep a real fixture so these checks do not depend on an installed AVIF encoder.
AVIF = base64.b64decode(
    'AAAAIGZ0eXBhdmlmAAAAAGF2aWZtaWYxbWlhZk1BMUIAAAGGbWV0YQAAAAAAAAAhaGRscgAAAAAAAAAAcGljdAAAAAAAAAAAAAAAAAAAAAAOcGl0bQAAAAAAAQAAACxpbG9jAAAAAEQAAAIAAQAAAAEAAAHNAAAAIgACAAAAAQAAAa4AAAAfAAAAQmlpbmYAAAAAAAIAAAAaaW5mZQIAAAAAAQAAYXYwMUNvbG9yAAAAABppbmZlAgAAAAACAABhdjAxQWxwaGEAAAAAGmlyZWYAAAAAAAAADmF1eGwAAgABAAEAAADDaXBycAAAAJ1pcGNvAAAAFGlzcGUAAAAAAAAAAgAAAAIAAAAQcGl4aQAAAAADCAgIAAAADGF2MUOBAAwAAAAAE2NvbHJuY2x4AAEADQAGgAAAAA5waXhpAAAAAAEIAAAADGF2MUOBABwAAAAAOGF1eEMAAAAAdXJuOm1wZWc6bXBlZ0I6Y2ljcDpzeXN0ZW1zOmF1eGlsaWFyeTphbHBoYQAAAAAeaXBtYQAAAAAAAAACAAEEAQKDBAACBAEFhgcAAABJbWRhdBIACgQYADYVMhUUAAwxAPd66Yf4PCAccufJU18PUGASAAoFGAA2BCAyFxQAAwwwxADuYXZAGpVgsNZtOs3N49a+'
)


class AvifAssetsTests(unittest.TestCase):
    def test_registered_artwork_preserves_original_bytes_and_mime(self):
        name = 'Report/StaticResources/RegisteredResources/Transparent.AVIF'
        model = {'pages': []}
        enrich_report(model, {name: AVIF, 'outside.avif': AVIF})
        self.assertEqual(set(model['assets']), {name, 'Transparent.AVIF'})
        asset = model['assets'][name]
        self.assertEqual(asset, model['assets']['Transparent.AVIF'])
        self.assertTrue(asset.startswith('data:image/avif;base64,'))
        self.assertEqual(base64.b64decode(asset.split(',', 1)[1]), AVIF)
        self.assertIn(b'Alpha', AVIF)

    def test_existing_per_asset_and_total_limits_apply_to_avif(self):
        folder = 'Report/StaticResources/RegisteredResources/'
        limit = 8 * 1024 ** 2
        boundary = AVIF + b'\0' * (limit - len(AVIF))
        files = {folder + 'oversized.avif': boundary + b'\0'}
        files.update({folder + str(i) + '.avif': boundary for i in range(4)})
        files[folder + 'over-total.avif'] = AVIF
        model = {'pages': []}
        enrich_report(model, files)
        self.assertNotIn('oversized.avif', model['assets'])
        self.assertNotIn('over-total.avif', model['assets'])
        self.assertEqual(len(model['assets']), 8)  # Full paths and basename aliases.
        for i in range(4):
            self.assertEqual(len(base64.b64decode(model['assets'][str(i) + '.avif'].split(',', 1)[1])), limit)

    def test_inert_avif_images_inside_svg_survive_sanitization(self):
        uri = 'data:image/avif;base64,' + base64.b64encode(AVIF).decode('ascii')
        source = ('<svg xmlns="http://www.w3.org/2000/svg"><image href="' + uri + '"/>'
                  '<image href="https://example.org/remote.avif"/>'
                  '<image href="data:text/html;base64,PHNjcmlwdD4="/></svg>').encode()
        result = safe_svg(source)
        self.assertIn(uri.encode(), result)
        self.assertNotIn(b'example.org', result)
        self.assertNotIn(b'data:text/html', result)


if __name__ == '__main__':
    unittest.main()
