import json
import unittest
from presentation import visible_model, enrich_report, classify_tooltip_pages
class TooltipPageTests(unittest.TestCase):
    @staticmethod
    def assignment(section,show=True,kind='Canvas',alias='visualContainerObjects'):
        literal=lambda value:{'expr':{'Literal':{'Value':value}}}
        props={'type':literal("'"+kind+"'"),'section':literal("'"+section+"'"),'show':literal(str(show).lower())}
        return {'definition':{alias:{'visualTooltip':[{'properties':props}]}}}

    def test_hidden_tooltip_available_without_navigation_or_admin_pages(self):
        ref=lambda name:{'expr':{'ResourcePackageItem':{'ItemName':name}}}
        model={'pages':[{'id':'main','visuals':[]},{'id':'tip','hidden':True,'isTooltip':True,'visuals':[ref('tip.png')]},{'id':'secret','hidden':True,'visuals':[ref('private.png')]}],'assets':{'tip.png':'tooltip-art','private.png':'admin-art'},'bookmarks':[]}
        result=visible_model(model,{'isAdmin':False})
        self.assertEqual([p['id'] for p in result['pages']],['main'])
        self.assertEqual([p['id'] for p in result['tooltipPages']],['tip'])
        self.assertEqual(result['assets'],{'tip.png':'tooltip-art'})
        self.assertEqual(len(model['pages']),3)
        self.assertIs(visible_model(model,{'isAdmin':True}),model)

    def test_legacy_numeric_page_classified_by_canvas_assignment_on_import(self):
        visual=self.assignment('tip',alias='vcObjects')
        visual.update(id='matrix',type='pivotTable')
        model={'pages':[{'id':'main','visuals':[visual]},{'id':'tip','hidden':True,'visuals':[]},{'id':'secret','hidden':True,'visuals':[]}]}
        sections=[{'name':'main','config':'{}'},{'name':'tip','config':json.dumps({'type':1})},{'name':'secret','config':json.dumps({'type':1})}]
        enrich_report(model,{'Report/Layout':json.dumps({'sections':sections}).encode('utf-16-le')})
        self.assertTrue(model['pages'][1]['isTooltip'])
        self.assertEqual(model['pages'][1]['tooltipClassification'],'visualAssignment')
        self.assertFalse(model['pages'][2]['isTooltip'])
        reader=visible_model(model,{'isAdmin':False})
        self.assertEqual([p['id'] for p in reader['pages']],['main'])
        self.assertEqual([p['id'] for p in reader['tooltipPages']],['tip'])

    def test_existing_saved_model_upgraded_without_exposing_hidden_navigation(self):
        model={'pages':[{'id':'main','visuals':[self.assignment('tip')]},{'id':'tip','hidden':True,'pageType':1,'isTooltip':False,'visuals':[]},{'id':'secret','hidden':True,'visuals':[]}], 'bookmarks':[]}
        reader=visible_model(model,{'isAdmin':False})
        self.assertEqual([p['id'] for p in reader['tooltipPages']],['tip'])
        self.assertEqual([p['id'] for p in reader['pages']],['main'])
        self.assertTrue(visible_model(model,{'isAdmin':True})['pages'][1]['isTooltip'])
        model['pages'][0]['visuals'][0]=self.assignment('tip',show=False)
        self.assertEqual(visible_model(model,{'isAdmin':False})['tooltipPages'],[])

    def test_disabled_default_unknown_and_unreachable_assignments_do_not_expose_pages(self):
        visuals=[self.assignment('disabled',show=False),self.assignment('default',kind='Default'),self.assignment('absent')]
        model={'pages':[{'id':'main','visuals':visuals},{'id':'disabled','hidden':True,'visuals':[]},{'id':'default','hidden':True,'visuals':[]},{'id':'private-source','hidden':True,'visuals':[self.assignment('secret')]},{'id':'secret','hidden':True,'visuals':[]}]}
        self.assertEqual(visible_model(model,{'isAdmin':False})['tooltipPages'],[])

    def test_reachable_nested_tooltip_assignments_and_legacy_config_binding(self):
        model={'pages':[{'id':'main','visuals':[self.assignment('tip')]},{'id':'tip','hidden':True,'visuals':[self.assignment('nested')]},{'id':'nested','hidden':True,'visuals':[]}]}
        classify_tooltip_pages(model)
        self.assertEqual([p['id'] for p in visible_model(model,{'isAdmin':False})['tooltipPages']],['tip','nested'])
        bound={'pages':[{'id':'bound','hidden':True,'visuals':[]}]}
        layout={'sections':[{'name':'bound','config':json.dumps({'pageBinding':{'type':'Tooltip'}})}]}
        enrich_report(bound,{'Report/Layout':json.dumps(layout).encode()})
        self.assertTrue(bound['pages'][0]['isTooltip'])
        bound['pages'][0]['isTooltip']=False
        self.assertEqual([p['id'] for p in visible_model(bound,{'isAdmin':False})['tooltipPages']],['bound'])

    def test_dynamic_and_malformed_assignments_are_not_evaluated(self):
        visual=self.assignment('tip')
        visual['definition']['visualContainerObjects']['visualTooltip'][0]['properties']['section']={'expr':{'Measure':{'Property':'Page name'}}}
        model={'pages':[{'id':'main','visuals':[visual,{'definition':{'vcObjects':None}},{'definition':{'vcObjects':{'visualTooltip':[None,{'properties':None}]}}}]},{'id':'tip','hidden':True,'visuals':[]}]}
        self.assertEqual(visible_model(model,{'isAdmin':False})['tooltipPages'],[])
if __name__=='__main__':unittest.main()
