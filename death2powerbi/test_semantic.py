"""Run: py test_semantic.py "path/to/Life in Europe.pbix""""
import sys
from pbixray import PBIXRay
from semantic_model import extract_relationships

model=PBIXRay(sys.argv[1])
relationships=extract_relationships(model,[str(t) for t in model.tables])
found=relationships[(relationships.FromTableName=='Population') & (relationships.ToTableName=='Countries')]
assert len(found)==1 and int(found.iloc[0].IsActive)==1
assert found.iloc[0].FromColumnName==found.iloc[0].ToColumnName=='Country'
assert found.iloc[0].Cardinality=='M:1'
assert len(relationships)==13
print('PASS: all 13 logical relationships retained, including active Population -> calculated Countries')
