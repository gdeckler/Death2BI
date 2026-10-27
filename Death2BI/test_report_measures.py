import unittest,json
from semantic_model import merge_report_measures
class ReportMeasuresTests(unittest.TestCase):
 def test_merge_local_measures_without_losing_model_measures(self):
  result={'measures':[{'TableName':'Model','Name':'Base','Expression':'1'},{'TableName':'Local','Name':'Rate','Expression':'0'}]}
  files={'Project.Report/definition/reportExtensions.json':json.dumps({'entities':[{'name':'Local','measures':[{'name':'Rate','expression':'[Base]/2','formatString':'0.0%'},{'name':'Artwork','expression':'"data:image/svg+xml;utf8,<svg/>"','dataCategory':'ImageUrl'}]}]}).encode()}
  merge_report_measures(result,files);merge_report_measures(result,files)
  self.assertEqual(len(result['measures']),3)
  self.assertEqual(result['measures'][1]['FormatString'],'0.0%')
  self.assertEqual(result['measures'][2]['DataCategory'],'ImageUrl')
if __name__=='__main__':unittest.main()
