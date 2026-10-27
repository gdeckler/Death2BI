"""Selection-pane visibility is imported without removing hidden filter state."""
import copy
import json
import unittest

from presentation import enrich_report, visual_hidden


class PresentationVisibilityTests(unittest.TestCase):
    def test_modern_flags_and_legacy_display_precedence(self):
        hidden = {'visual': {'display': {'mode': 'hidden'}}}
        for source, expected in [
            ({}, False),
            (hidden, True),
            ({'visual': {'display': {'mode': 'visible'}}}, False),
            ({**hidden, 'isHidden': True}, True),
            ({**hidden, 'isHidden': False}, False),
            ({'isHidden': True}, True),
            ({'isHidden': False}, False),
            ({'isHidden': 'false'}, False),
            ({'isHidden': 'true'}, False),
            ({'isHidden': 1}, False),
            ({**hidden, 'isHidden': 'false'}, True),
            ({**hidden, 'isHidden': None}, True),
            ({'visual': {'display': None}}, False),
            ({'visual': None}, False),
        ]:
            with self.subTest(source=source):
                original = copy.deepcopy(source)
                self.assertIs(visual_hidden(source), expected)
                self.assertEqual(source, original)

    def test_legacy_hidden_slicer_and_group_filters_are_retained(self):
        field = {'Column': {'Expression': {'SourceRef': {'Entity': 'Customers'}}, 'Property': 'Segment'}}
        selection = {'filter': {'Where': [{'Condition': {'In': {
            'Expressions': [field], 'Values': [[{'Literal': {'Value': "'Business'"}}]],
        }}}]}}
        definition = {'visualType': 'slicer', 'display': {'mode': 'hidden'},
                      'objects': {'general': [{'properties': {'filter': selection}}]},
                      'query': {'queryState': {'Values': {'projections': [{'field': field, 'queryRef': 'Customers.Segment'}]}}}}
        child_definition = {'visualType': 'slicer', 'display': {'mode': 'visible'},
                            'query': copy.deepcopy(definition['query'])}
        configs = [
            {'name': 'hiddenSlicer', 'singleVisual': definition},
            {'name': 'hiddenGroup', 'isHidden': True, 'singleVisualGroup': {'displayName': 'Filters'}},
            {'name': 'inheritedSlicer', 'parentGroupName': 'hiddenGroup', 'singleVisual': child_definition},
        ]
        containers = [{'x': 10, 'y': 20, 'width': 100, 'height': 100, 'z': i,
                       'config': json.dumps(config)} for i, config in enumerate(configs)]
        layout = {'sections': [{'name': 'page', 'visualContainers': containers}]}
        model = {'pages': [{'id': 'page', 'visuals': [
            {'id': 'hiddenSlicer', 'type': 'slicer', 'definition': copy.deepcopy(definition), 'filters': [copy.deepcopy(selection)]},
            {'id': 'hiddenGroup', 'type': 'unknown', 'definition': {}},
            {'id': 'inheritedSlicer', 'type': 'slicer', 'definition': copy.deepcopy(child_definition)},
        ]}]}
        before = copy.deepcopy(layout)
        enrich_report(model, {'Report/Layout': json.dumps(layout).encode('utf-16-le')})
        visuals = {v['id']: v for v in model['pages'][0]['visuals']}
        self.assertTrue(visuals['hiddenSlicer']['ownHidden'])
        self.assertTrue(visuals['hiddenSlicer']['hidden'])
        self.assertEqual(visuals['hiddenSlicer']['filters'], [selection])
        self.assertEqual(visuals['hiddenSlicer']['definition']['objects']['general'][0]['properties']['filter'], selection)
        self.assertEqual(visuals['hiddenSlicer']['definition']['query'], definition['query'])
        self.assertEqual(visuals['hiddenSlicer']['definition']['display'], {'mode': 'hidden'})
        self.assertTrue(visuals['hiddenGroup']['hidden'])
        self.assertEqual(visuals['hiddenGroup']['type'], 'group')
        self.assertFalse(visuals['inheritedSlicer']['ownHidden'])
        self.assertTrue(visuals['inheritedSlicer']['hidden'])
        self.assertEqual(visuals['inheritedSlicer']['groupChain'], ['hiddenGroup'])
        self.assertEqual((visuals['inheritedSlicer']['x'], visuals['inheritedSlicer']['y']), (20, 40))
        self.assertEqual(layout, before)

    def test_pbir_explicit_visible_and_hidden_group_inheritance(self):
        sources = [
            {'name': 'group', 'visualGroup': {'displayName': 'Filters'}, 'isHidden': True},
            {'name': 'child', 'parentGroupName': 'group', 'isHidden': False, 'visual': {'visualType': 'slicer'}},
            {'name': 'shown', 'isHidden': False, 'visual': {'visualType': 'slicer', 'display': {'mode': 'hidden'}}},
            {'name': 'hidden', 'isHidden': True, 'visual': {'visualType': 'slicer', 'display': {'mode': 'visible'}}},
        ]
        model = {'pages': [{'id': 'page', 'visuals': [
            {'id': x['name'], 'type': 'group' if 'visualGroup' in x else 'slicer', 'definition': copy.deepcopy(x.get('visual', {}))}
            for x in sources]}]}
        files = {'Report/definition/pages/page/visuals/' + x['name'] + '/visual.json': json.dumps(x).encode()
                 for x in sources}
        before = copy.deepcopy(files)
        enrich_report(model, files)
        visuals = {v['id']: v for v in model['pages'][0]['visuals']}
        self.assertTrue(visuals['child']['hidden'])
        self.assertFalse(visuals['child']['ownHidden'])
        self.assertFalse(visuals['shown']['hidden'])
        self.assertTrue(visuals['hidden']['hidden'])
        self.assertEqual(files, before)


if __name__ == '__main__':
    unittest.main()
