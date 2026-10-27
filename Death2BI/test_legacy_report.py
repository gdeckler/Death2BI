import json
import unittest
from server import report_pages


class LegacyReportTests(unittest.TestCase):
    def test_named_projections_aliases_sorts_titles_and_query_filters(self):
        column={'Column':{'Expression':{'SourceRef':{'Source':'d'}},'Property':'Month'}}
        measure={'Measure':{'Expression':{'SourceRef':{'Source':'e'}},'Property':'New Hires'}}
        visual={'visualType':'lineChart','projections':{'Category':[{'queryRef':'month','active':True}],'Y':[{'queryRef':'hires'}]},'prototypeQuery':{'Version':2,'From':[{'Name':'d','Entity':'Date'},{'Name':'e','Entity':'Employee'}],'Select':[{**column,'Name':'month','NativeReferenceName':'Month'},{**measure,'Name':'hires'}],'OrderBy':[{'Expression':column,'Direction':1}],'Where':[{'Condition':{'Comparison':{'ComparisonKind':0,'Left':column,'Right':{'Literal':{'Value':"'Jan'"}}}}}]},'vcObjects':{'title':[]}}
        layout={'sections':[{'name':'page','displayName':'Hires','visualContainers':[{'config':json.dumps({'name':'chart','singleVisual':visual})}]}]}
        pages=report_pages({'Report/Layout':json.dumps(layout).encode()})
        v=pages[0]['visuals'][0];definition=v['definition'];state=definition['query']['queryState']
        self.assertEqual(state['Category']['projections'][0]['field']['Column']['Expression']['SourceRef'],{'Entity':'Date'})
        self.assertEqual(state['Y']['projections'][0]['field']['Measure']['Property'],'New Hires')
        self.assertEqual(definition['query']['sortDefinition']['sort'][0]['direction'],'Ascending')
        self.assertEqual(definition['visualContainerObjects'],{'title':[]})
        self.assertEqual(v['filters'][0]['filter']['Where'],visual['prototypeQuery']['Where'])
        self.assertNotIn('query',visual)


if __name__=='__main__':unittest.main()
