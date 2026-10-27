import copy
import json
import unittest
from pathlib import Path
from presentation import separate_navigation_icons

class NavigationLayoutTests(unittest.TestCase):
    def test_compact_icons_separate_and_other_elements_stay_put(self):
        def icon(name,x,y,w,h):
            return dict(id=name,type='image',x=x,y=y,width=w,height=h,definition={'visualContainerObjects':{'general':[{'properties':{'altText':{'expr':{'Literal':{'Value':"'Navigate to page'"}}}}}]}})
        page={'width':1280,'height':720,'visuals':[icon('home',7,3,43,40),icon('a',45,3,29,26),icon('b',72,3,25,26),icon('c',46,23,25,26),icon('d',72,23,23,26),dict(id='decoration',type='image',x=15,y=59,width=63,height=62)]}
        decoration=copy.deepcopy(page['visuals'][-1])
        separate_navigation_icons(page)
        self.assertEqual(page['visuals'][-1],decoration)
        self.assertIn('navigationSourceBounds',page['visuals'][0])
        icons=page['visuals'][:-1]
        for i,a in enumerate(icons):
            for b in icons[i+1:]:
                self.assertTrue(a['x']+a['width']<=b['x'] or b['x']+b['width']<=a['x'] or a['y']+a['height']<=b['y'] or b['y']+b['height']<=a['y'])
        once=copy.deepcopy(page);separate_navigation_icons(page);self.assertEqual(page,once)

    def test_intentional_stacked_states_remain(self):
        v=dict(type='actionButton',x=0,y=0,width=30,height=30,definition={'objects':{'visualLink':[{'properties':{'type':"PageNavigation"}}]}})
        page={'visuals':[copy.deepcopy(v),copy.deepcopy(v)]}
        separate_navigation_icons(page)
        self.assertEqual(page['visuals'][0]['width'],30)
        self.assertNotIn('navigationSourceBounds',page['visuals'][0])

if __name__=='__main__':unittest.main()
