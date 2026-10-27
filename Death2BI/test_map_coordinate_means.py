"""Embedded coordinate means retain the map grain, fact counts and security."""
import copy
import unittest

import duckdb
from dax_engine import evaluate_visual


def column(table, name):
    return {'Column': {'Expression': {'SourceRef': {'Entity': table}}, 'Property': name}}


class MapCoordinateMeansTests(unittest.TestCase):
    def setUp(self):
        self.con = duckdb.connect(config={'threads': 1})
        self.addCleanup(self.con.close)
        self.con.execute('CREATE TABLE Regions(ID INTEGER,LGA VARCHAR,latitude DOUBLE,longitude DOUBLE)')
        self.con.execute("INSERT INTO Regions VALUES (1,'North',0,0),(2,'North',10,10),(3,'South',20,20),"
                         "(4,'Invalid',20,181),(5,'Invalid',91,30),(6,'Invalid',20,NULL),(7,'Invalid',NULL,40),"
                         "(8,'Mixed',50,50),(9,'Mixed',30,181),(10,'Mixed',91,30),(11,'Mixed',20,NULL),(12,'Mixed',NULL,40)")
        self.con.execute('CREATE TABLE Visits(RegionID INTEGER,Year INTEGER)')
        self.con.execute('INSERT INTO Visits SELECT 1,2025 FROM range(10)')
        self.con.execute('INSERT INTO Visits VALUES (2,2026),(3,2026),(3,2026),(4,2026),(5,2026),(6,2026),(7,2026),'
                         '(8,2026),(9,2026),(10,2026),(11,2026),(12,2026)')
        self.model = {'tables': [{'name': 'Regions'}, {'name': 'Visits'}], 'relationships': [{
            'IsActive': True, 'Cardinality': 'M:1', 'CrossFilteringBehavior': 'Single',
            'FromTableName': 'Visits', 'FromColumnName': 'RegionID', 'ToTableName': 'Regions', 'ToColumnName': 'ID'}],
            'measures': [{'TableName': 'M', 'Name': 'Total Visits', 'Expression': 'COUNTROWS(Visits)'}]}
        self.fields = [{'Measure': {'Expression': {'SourceRef': {'Entity': 'M'}}, 'Property': 'Total Visits'}},
                       column('Regions', 'LGA'),
                       {'GeoMean': {'table': 'Regions', 'column': 'latitude', 'latitude': 'latitude', 'longitude': 'longitude'}},
                       {'GeoMean': {'table': 'Regions', 'column': 'longitude', 'latitude': 'latitude', 'longitude': 'longitude'}}]

    def evaluate(self, names=('North', 'South', 'Invalid', 'Mixed'), base=None):
        groups = [{'values': {'1': name}, 'filters': [{'table': 'Regions', 'columns': ['LGA'],
                   'sql': '"Regions"."LGA" = \''+name+'\''}], 'scope': [['Regions', 'LGA']]} for name in names]
        payload = {'fields': self.fields, 'groups': groups, 'baseFilters': base or []}
        before = copy.deepcopy((self.model, payload))
        result = evaluate_visual(self.con, self.model, payload)
        self.assertEqual((self.model, payload), before, 'coordinate enrichment must preserve source fields and filters')
        return result['rows']

    def test_countrows_fact_is_not_duplicated_or_reweighted_by_coordinate_rows(self):
        rows = self.evaluate()
        self.assertEqual(rows, [[11, 'North', 5, 5], [2, 'South', 20, 20],
                                [4, 'Invalid', None, None], [5, 'Mixed', 50, 50]])
        weighted = self.con.execute('SELECT AVG(r.latitude) FROM Visits v JOIN Regions r ON r.ID=v.RegionID WHERE r.LGA=\'North\'').fetchone()[0]
        self.assertNotEqual(weighted, rows[0][2], 'geographic means describe region rows, not visit-weighted fact joins')

    def test_source_fact_and_dimension_filters_preserve_their_relationship_direction(self):
        year = {'table': 'Visits', 'columns': ['Year'], 'sql': '"Visits"."Year"=2026'}
        self.assertEqual(self.evaluate(('North',), [year]), [[1, 'North', 5, 5]],
                         'a one-way fact-year filter changes visits without moving the location centroid')
        address = {'table': 'Regions', 'columns': ['ID'], 'sql': '"Regions"."ID"=2'}
        self.assertEqual(self.evaluate(('North',), [address]), [[1, 'North', 10, 10]])

    def test_secured_coordinate_and_fact_views_are_both_respected(self):
        self.con.execute('ALTER TABLE Regions RENAME TO RawRegions')
        self.con.execute('CREATE VIEW Regions AS SELECT * FROM RawRegions WHERE ID<>2')
        self.assertEqual(self.evaluate(('North',)), [[10, 'North', 0, 0]],
                         'denied coordinate rows cannot affect coordinates or related visit counts')
        self.con.execute('ALTER TABLE Visits RENAME TO RawVisits')
        self.con.execute('CREATE VIEW Visits AS SELECT * FROM RawVisits WHERE RegionID<>1')
        self.assertEqual(self.evaluate(('North',)), [[None, 'North', 0, 0]],
                         'an empty secured fact domain retains DAX COUNTROWS BLANK while coordinates stay secured')


if __name__ == '__main__':
    unittest.main()
