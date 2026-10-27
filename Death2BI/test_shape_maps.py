import unittest
from shape_maps import features
class ShapeMapTests(unittest.TestCase):
 def test_topology(self):
  d={'type':'Topology','transform':{'scale':[2,3],'translate':[10,20]},'arcs':[[[0,0],[1,0],[0,1],[-1,-1]]],'objects':{'x':{'type':'GeometryCollection','geometries':[{'type':'Polygon','arcs':[[0]],'properties':{'name':'A'},'id':'1'},{'type':'Polygon','arcs':[[-1]],'properties':{'name':'B'}}]}}}
  f=features(d);self.assertEqual(f[0]['geometry']['coordinates'][0],[[10,20],[12,20],[12,23],[10,20]]);self.assertEqual(f[1]['geometry']['coordinates'][0],f[0]['geometry']['coordinates'][0][::-1]);self.assertEqual(f[0]['properties']['keys'],['A','1'])
 def test_geojson(self):
  d={'type':'FeatureCollection','features':[{'type':'Feature','properties':{'region':'X'},'geometry':{'type':'Polygon','coordinates':[]}}]}
  self.assertEqual(features(d)[0]['properties']['name'],'X');self.assertNotIn('keys',d['features'][0]['properties'])
if __name__=='__main__':unittest.main()
