"""Legacy selection-pane groups retain initial visibility and child ownership."""
import copy
import json
import unittest

from presentation import enrich_report, visual_hidden


class GroupVisibilityTests(unittest.TestCase):
    def test_legacy_group_flag_is_distinct_from_root_and_child_visibility(self):
        for source, expected in [
            ({'visualGroup': {'isHidden': True}}, True),
            ({'visualGroup': {'isHidden': False}}, False),
            ({'singleVisualGroup': {'isHidden': True}}, True),
            ({'singleVisualGroup': {'isHidden': False}}, False),
            ({'visualGroup': {'isHidden': 'true'}}, False),
            ({'visualGroup': {'isHidden': 1}}, False),
            ({'isHidden': False, 'visualGroup': {'isHidden': True}}, False),
            ({'isHidden': True, 'visualGroup': {'isHidden': False}}, True),
            ({'isHidden': False, 'singleVisualGroup': {'isHidden': True}}, False),
        ]:
            with self.subTest(source=source):
                original = copy.deepcopy(source)
                self.assertIs(visual_hidden(source), expected)
                self.assertEqual(source, original)

    def test_hidden_story_group_with_four_visible_children_repairs_cached_model(self):
        # Source-shaped legacy Story1/Story2 groups: group visibility lives in
        # singleVisualGroup, not at the root of the visual container config.
        groups = [('story1', False), ('story2', True)]
        definitions = {}
        configs = []
        for group, hidden in groups:
            configs.append({'name': group, 'singleVisualGroup': {
                'displayName': group, 'groupMode': 0, 'isHidden': hidden,
            }})
            for index in range(4):
                name = group + '-child-' + str(index)
                definition = {'visualType': 'textbox', 'display': {'mode': 'visible'},
                              'objects': {'general': [{'properties': {'text': name}}]}}
                definitions[name] = definition
                configs.append({'name': name, 'parentGroupName': group,
                                'singleVisual': definition})
        definitions['hidden-chart'] = {'visualType': 'clusteredBarChart',
                                       'display': {'mode': 'hidden'}}
        configs.append({'name': 'hidden-chart', 'singleVisual': definitions['hidden-chart']})
        containers = [{'x': 10, 'y': 20, 'width': 100, 'height': 80, 'z': index,
                       'config': json.dumps(config)} for index, config in enumerate(configs)]
        snapshots = {}
        for group, _ in groups:
            snapshots[group] = {
                'name': group, 'displayName': group,
                'options': {'targetVisualNames': [], 'suppressData': True},
                'explorationState': {'activeSection': 'stories', 'sections': {'stories': {
                    'visualContainerGroups': {
                        name: {'isHidden': name != group} for name, _ in groups
                    },
                    'visualContainers': {name: {'singleVisual': {}}
                                         for name in definitions if name != 'hidden-chart'},
                }}},
            }
        report = {'config': json.dumps({'bookmarks': list(snapshots.values())}),
                  'sections': [{'name': 'stories', 'visualContainers': containers}]}
        # A previously converted cached model has incorrect false flags. Enrich
        # must replace them from source rather than trusting or OR-ing them.
        model = {'pages': [{'id': 'stories', 'visuals': [
            {'id': config['name'], 'type': 'group' if 'singleVisualGroup' in config else definitions[config['name']]['visualType'],
             'ownHidden': False, 'hidden': False,
             'definition': copy.deepcopy(definitions.get(config['name'], {}))}
            for config in configs
        ]}]}
        encoded = {'Report/Layout': json.dumps(report).encode('utf-16-le')}
        source_before = copy.deepcopy(encoded)
        enrich_report(model, encoded)
        by_id = {visual['id']: visual for visual in model['pages'][0]['visuals']}
        self.assertFalse(by_id['story1']['ownHidden'])
        self.assertFalse(by_id['story1']['hidden'])
        self.assertTrue(by_id['story2']['ownHidden'])
        self.assertTrue(by_id['story2']['hidden'])
        for group, hidden in groups:
            for index in range(4):
                child = by_id[group + '-child-' + str(index)]
                self.assertFalse(child['ownHidden'], 'children retain their own visible state for bookmark reveal')
                self.assertIs(child['hidden'], hidden)
                self.assertEqual(child['groupChain'], [group])
                self.assertEqual(child['definition'], definitions[child['id']])
        self.assertTrue(by_id['hidden-chart']['ownHidden'])
        self.assertTrue(by_id['hidden-chart']['hidden'])
        self.assertEqual(model['bookmarks'], list(snapshots.values()))
        self.assertEqual(encoded, source_before)
        first = copy.deepcopy(model)
        enrich_report(model, encoded)
        self.assertEqual(model, first, 'repairing an already enriched cached model is idempotent')


if __name__ == '__main__':
    unittest.main()
