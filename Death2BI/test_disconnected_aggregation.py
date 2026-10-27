"""Execute the shared JS compiler plan supplied on stdin against DuckDB."""
import duckdb,json,sys
def main():
    plan=json.load(sys.stdin)
    c=duckdb.connect()
    c.execute('CREATE TABLE Fact(Amount INTEGER)')
    c.execute('INSERT INTO Fact VALUES (10),(20),(NULL)')
    c.execute('CREATE TABLE Category(Name VARCHAR)')
    c.execute("INSERT INTO Category VALUES ('A'),('B'),('A')")
    r=c.execute(plan['sql']).fetchall()
    assert r==[('A',30,15.0,2),('B',30,15.0,2)],r
    filtered=c.execute(plan['filtered']).fetchall()
    assert filtered==[('B',20,20.0,1)],filtered
    c.execute('DELETE FROM Fact')
    r=c.execute(plan['sql']).fetchall()
    assert r==[('A',None,None,0),('B',None,None,0)],r
    print('PASS disconnected SUM/AVG/DISTINCTCOUNT, duplicate domains and empty fact semantics')

if __name__=='__main__':main()
