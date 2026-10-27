import unittest,copy,duckdb
from report_schema import audit_documents,normalize_definition
from presentation import enrich_report
from dax_engine import evaluate_visual,Evaluator,Parser
class CompatibilityFoundationTests(unittest.TestCase):
 def test_offline_schema_and_unknown_preservation(self):
  uri='https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json'
  doc={'$schema':uri,'version':'1.0','artifacts':[{'report':{'path':'../Report'}}],'futureExtension':True}
  result=audit_documents({'x.pbip':doc});self.assertTrue(result['diagnostics']);self.assertTrue(doc['futureExtension'])
  unknown=audit_documents({'page.json':{'$schema':uri.replace('1.0.0','99.0.0')}});self.assertEqual(unknown['diagnostics'][0]['code'],'unsupported-schema-version')
  self.assertEqual(normalize_definition({'vcObjects':{'a':1},'unknown':2},True)['visualContainerObjects'],{'a':1})
 def test_nested_schema_references_validate_offline(self):
  uri='https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.9.0/schema.json'
  doc={'$schema':uri,'name':'v','position':{'x':0,'y':0,'z':0,'width':100,'height':100,'tabOrder':0},'visual':{'visualType':'card','query':{'queryState':{}}}}
  self.assertEqual(audit_documents({'visual.json':doc})['diagnostics'],[])
  doc['position']['width']='wide';self.assertTrue(any(d['path']=='/position/width' for d in audit_documents({'visual.json':doc})['diagnostics']))
 def test_theme_authored_inheritance_not_inferred(self):
  import json
  files={k:json.dumps(v).encode() for k,v in {'report.json':{'themeCollection':{'baseTheme':{'name':'Base'},'customTheme':{'name':'Custom'}}},'Base.json':{'background':'#fff','secondaryBackground':'#eee','foregroundNeutralSecondary':'#616161'},'Custom.json':{'background':'#111','foreground':'#eee'}}.items()}
  r={'pages':[]};enrich_report(r,files);self.assertEqual(r['theme']['secondaryBackground'],'#eee');self.assertEqual(r['theme']['foregroundNeutralSecondary'],'#616161');self.assertEqual(r['formattingProvenance']['fallbacks'],[]);self.assertIn('secondaryBackground',r['theme']['_inheritedStructuralColors'])
 def test_dynamic_formats_context_numeric_values_unchanged(self):
  c=duckdb.connect();self.addCleanup(c.close);c.execute("CREATE TABLE T(Category VARCHAR,Amount DOUBLE);INSERT INTO T VALUES ('A',20),('B',200)")
  model={'tables':[{'name':'T'}],'relationships':[],'measures':[{'TableName':'M','Name':'Sales','Expression':'SUM(T[Amount])','FormatString':'0.0','FormatStringExpression':'IF(SELECTEDMEASURE()>100,"$0.00","0.0%")'}]}
  field={'Measure':{'Expression':{'SourceRef':{'Entity':'M'}},'Property':'Sales'}}
  groups=[{'measureValues':[v],'filters':[{'table':'T','columns':['Category'],'sql':"T.Category='"+cat+"'"}]} for cat,v in [('A',20),('B',200)]]
  result=evaluate_visual(c,model,{'operation':'formats','fields':[field],'groups':groups,'baseFilters':[]});self.assertEqual(result['rowFormats'],[['0.0%'],['$0.00']]);self.assertEqual(groups[0]['measureValues'],[20])
  model['measures'][0]['FormatStringExpression']='IF(SELECTEDVALUE(T[Category])="A","0.00",SELECTEDMEASUREFORMATSTRING())'
  self.assertEqual(evaluate_visual(c,model,{'operation':'formats','fields':[field],'groups':groups,'baseFilters':[]})['rowFormats'],[['0.00'],['0.0']])
 def test_blank_strict_loose_ordered_semantics(self):
  c=duckdb.connect();self.addCleanup(c.close);e=Evaluator(c,{'tables':[],'measures':[],'relationships':[]},{})
  for expr,expected in [('BLANK()=0',True),('BLANK()==0',False),('BLANK()=""',True),('BLANK()<=5',True),('BLANK()>0',False)]:self.assertEqual(e.run(Parser(expr).parse(),{},None),expected,expr)
if __name__=='__main__':unittest.main()
