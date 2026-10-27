"""Scalar DAX functions. All dispatch is explicit; no uploaded code is executed."""
import calendar
import inspect
import operator
import datetime as dt
import math
import re
from decimal import Decimal, ROUND_HALF_UP, ROUND_UP, ROUND_DOWN

FUNCTIONS = {}
DEFAULT_ARGUMENTS = {}
MISSING = object()
def register(name, minimum, maximum=None, family='Math and trig'):
    def wrap(fn):
        FUNCTIONS[name] = (minimum, minimum if maximum is None else maximum, family, fn)
        DEFAULT_ARGUMENTS[name] = {i:p.default for i,p in enumerate(inspect.signature(fn).parameters.values()) if p.kind in (p.POSITIONAL_ONLY,p.POSITIONAL_OR_KEYWORD) and p.default is not inspect.Parameter.empty}
        return fn
    return wrap

def number(v):
    if v is None: return 0
    if isinstance(v,dt.datetime):return (v-dt.datetime(1899,12,30)).total_seconds()/86400
    if isinstance(v,dt.date):return (v-dt.date(1899,12,30)).days
    if isinstance(v, bool): return int(v)
    if isinstance(v, (int,float,Decimal)): return v
    if isinstance(v,str) and re.fullmatch(r"[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?",v.strip()):v=v.strip().replace(",", "")
    try: return float(v)
    except (ValueError,TypeError): raise ValueError('DAX value cannot be converted to a number')
def numeric_pair(a,b):
    a,b=number(a),number(b)
    if isinstance(a,Decimal) and isinstance(b,float) or isinstance(b,Decimal) and isinstance(a,float):return float(a),float(b)
    return a,b

def text(v):
    if v is None: return ''
    if isinstance(v,bool): return 'TRUE' if v else 'FALSE'
    return str(v)
def date(v):
    if isinstance(v,dt.datetime): return v
    if isinstance(v,dt.date): return dt.datetime.combine(v,dt.time())
    if isinstance(v,str):
        try: return dt.datetime.fromisoformat(v)
        except ValueError: raise ValueError('Date text must use ISO YYYY-MM-DD format')
    if isinstance(v,(int,float)): return dt.datetime(1899,12,30)+dt.timedelta(days=v)
    raise ValueError('Expected a DAX date value')
def integer(v): return int(number(v))
def round_dax(v,digits=0,mode=ROUND_HALF_UP):
    digits=integer(digits)
    if abs(digits)>100: raise ValueError('DAX rounding precision exceeds limit')
    return float(Decimal(str(number(v))).quantize(Decimal(10)**-digits,rounding=mode))
def month_shift(value,months,end=False):
    value=date(value); y,m=divmod(value.year*12+value.month-1+integer(months),12); m+=1
    return value.replace(year=y,month=m,day=calendar.monthrange(y,m)[1] if end else min(value.day,calendar.monthrange(y,m)[1]))
def wildcard(pattern):
    result='';i=0
    while i<len(pattern):
        ch=pattern[i]
        if ch=='~' and i+1<len(pattern): i+=1; result+=re.escape(pattern[i])
        else: result+= '.*' if ch=='*' else '.' if ch=='?' else re.escape(ch)
        i+=1
    return result

# Arithmetic, rounding and transcendental functions.
for name,fn in {'ABS':abs,'ACOS':math.acos,'ACOSH':math.acosh,'ASIN':math.asin,'ASINH':math.asinh,'ATAN':math.atan,'ATANH':math.atanh,'COS':math.cos,'COSH':math.cosh,'SIN':math.sin,'SINH':math.sinh,'TAN':math.tan,'TANH':math.tanh,'SQRT':math.sqrt,'EXP':math.exp,'LN':math.log,'LOG10':math.log10,'DEGREES':math.degrees,'RADIANS':math.radians,'SIGN':lambda x:(x>0)-(x<0),'INT':math.floor}.items():
    register(name,1)(lambda x,fn=fn:fn(number(x)))
register('PI',0)(lambda:math.pi)
@register('POWER',2)
def power(a,b):
    a,b=numeric_pair(a,b)
    if abs(b)>10000 or isinstance(a,int) and isinstance(b,int) and b>0 and a.bit_length()*b>100000:
        raise RuntimeError('POWER exceeds the numeric computation limit')
    return a**b
register('LOG',1,2)(lambda a,b=10:math.log(number(a),number(b)))
register('MOD',2)(lambda a,b:operator.mod(*numeric_pair(a,b)))
register('QUOTIENT',2)(lambda a,b:math.trunc(operator.truediv(*numeric_pair(a,b))))
register('ROUND',2)(lambda a,b:round_dax(a,b))
register('ROUNDUP',2)(lambda a,b:round_dax(a,b,ROUND_UP))
register('ROUNDDOWN',2)(lambda a,b:round_dax(a,b,ROUND_DOWN))
register('TRUNC',1,2)(lambda a,b=0:round_dax(a,b,ROUND_DOWN))
@register('MROUND',2)
def mround(a,b):
    a,b=numeric_pair(a,b)
    if a*b<0: raise ValueError('MROUND arguments must have the same sign')
    return round_dax(a/b)*b if b else 0
@register('CEILING',2)
def ceiling(a,b):
    a,b=numeric_pair(a,b)
    if not b: return 0
    if a>0 and b<0: raise ValueError('Invalid CEILING significance')
    return math.ceil(a/abs(b))*abs(b) if b>0 else math.floor(a/abs(b))*abs(b)
@register('FLOOR',2)
def floor(a,b):
    a,b=numeric_pair(a,b)
    if not b: return 0
    if a*b<0: raise ValueError('FLOOR arguments must have the same sign')
    return math.floor(a/b)*b
register('EVEN',1)(lambda a:math.copysign(math.ceil(abs(number(a))/2)*2,number(a)))
register('ODD',1)(lambda a:math.copysign(2*math.floor(math.ceil(abs(number(a)))/2)+1,number(a)))
@register('FACT',1)
def fact(a):
    a=integer(a)
    if a<0 or a>170: raise ValueError('FACT requires an integer from 0 to 170')
    return math.factorial(a)
@register('COMBIN',2)
def combin(n,k):
    n,k=integer(n),integer(k)
    if not 0<=k<=n<=1000: raise ValueError('COMBIN argument limit exceeded')
    return math.comb(n,k)
def positive_integer_pair(a,b,fn):
    a,b=integer(a),integer(b)
    if a<0 or b<0: raise ValueError(fn+' requires nonnegative numbers')
    return a,b
register('GCD',2)(lambda a,b:math.gcd(*positive_integer_pair(a,b,'GCD')))
register('LCM',2)(lambda a,b:math.lcm(*positive_integer_pair(a,b,'LCM')))

# Logical and information functions. Branching/error functions are lazy in the evaluator.
for name,fn,arity in [('TRUE',lambda:True,0),('FALSE',lambda:False,0),('NOT',lambda x:not bool(x),1),('AND',lambda a,b:bool(a) and bool(b),2),('OR',lambda a,b:bool(a) or bool(b),2)]:
    register(name,arity,family='Logical')(fn)
for name,fn in {'ISBLANK':lambda x:x is None,'ISNUMBER':lambda x:isinstance(x,(int,float,Decimal)) and not isinstance(x,bool),'ISTEXT':lambda x:isinstance(x,str),'ISNONTEXT':lambda x:not isinstance(x,str),'ISLOGICAL':lambda x:isinstance(x,bool),'ISEVEN':lambda x:math.trunc(number(x))%2==0,'ISODD':lambda x:math.trunc(number(x))%2!=0}.items():
    register(name,1,family='Information')(fn)
register('BLANK',0,family='Logical')(lambda:None)
register('VALUE',1,family='Text')(number)

# Text functions. Search supports DAX wildcards, escape marker and one-based positions.
register('LEN',1,family='Text')(lambda x:len(text(x)))
register('LOWER',1,family='Text')(lambda x:text(x).lower())
register('UPPER',1,family='Text')(lambda x:text(x).upper())
register('TRIM',1,family='Text')(lambda x:re.sub(' +',' ',text(x).strip(' ')))
register('CONCATENATE',2,family='Text')(lambda a,b:text(a)+text(b))
register('EXACT',2,family='Text')(lambda a,b:text(a)==text(b))
@register('LEFT',1,2,'Text')
def left(value,count=1):
    if integer(count)<0: raise ValueError('LEFT count must be nonnegative')
    return text(value)[:integer(count)]
@register('RIGHT',1,2,'Text')
def right(value,count=1):
    if integer(count)<0: raise ValueError('RIGHT count must be nonnegative')
    return text(value)[-integer(count):] if integer(count) else ''
@register('MID',3,family='Text')
def mid(value,start,count):
    if integer(start)<1 or integer(count)<0: raise ValueError('Invalid MID position/count')
    return text(value)[integer(start)-1:integer(start)-1+integer(count)]
@register('REPLACE',4,family='Text')
def replace(value,start,count,replacement):
    if integer(start)<1 or integer(count)<0: raise ValueError('Invalid REPLACE position/count')
    value=text(value); start=integer(start)-1
    return value[:start]+text(replacement)+value[start+integer(count):]
@register('REPT',2,family='Text')
def rept(value,count):
    count=integer(count)
    if count<0 or len(text(value))*count>32767: raise ValueError('REPT result exceeds 32,767 characters')
    return text(value)*count
@register('SUBSTITUTE',3,4,'Text')
def substitute(value,old,new,instance=None):
    value,old,new=text(value),text(old),text(new)
    if not old: return value
    if instance is None: return value.replace(old,new)
    instance=integer(instance)
    if instance<1: raise ValueError('SUBSTITUTE instance must be positive')
    chunks=value.split(old)
    if len(chunks)<=instance:return value
    return old.join(chunks[:instance])+new+old.join(chunks[instance:])
@register('FIND',2,4,'Text')
def find(needle,value,start=1,notfound=MISSING):
    start=integer(start)
    if start<1 or start>len(text(value))+1: raise ValueError('Invalid FIND start position')
    pos=text(value).find(text(needle),start-1)
    if pos>=0:return pos+1
    if notfound is not MISSING:return notfound
    raise ValueError('FIND text was not found')
@register('SEARCH',2,4,'Text')
def search(needle,value,start=1,notfound=MISSING):
    start=integer(start)
    if start<1 or start>len(text(value))+1: raise ValueError('Invalid SEARCH start position')
    match=re.search(wildcard(text(needle)),text(value)[start-1:],re.I|re.S)
    if match:return start+match.start()
    if notfound is not MISSING:return notfound
    raise ValueError('SEARCH text was not found')
register('CONTAINSSTRING',2,family='Text')(lambda a,b:re.search(wildcard(text(b)),text(a),re.I|re.S) is not None)
register('CONTAINSSTRINGEXACT',2,family='Text')(lambda a,b:text(b) in text(a))
register('UNICHAR',1,family='Text')(lambda x:chr(integer(x)) if 0<integer(x)<=0x10ffff and not 0xd800<=integer(x)<=0xdfff else (_ for _ in ()).throw(ValueError('Invalid Unicode code point')))
register('UNICODE',1,family='Text')(lambda x:ord(text(x)[0]))

# Date functions use typed datetime values; ambiguous locale text is rejected.
@register('DATE',3,family='Date and time')
def make_date(year,month,day):
    year,month,day=integer(year),integer(month),integer(day)
    if 0<=year<=1899:year+=1900
    if month<1 or day<1:raise ValueError('DATE requires positive month/day')
    year,month=divmod(year*12+month-1,12)
    return dt.datetime(year,month+1,1)+dt.timedelta(days=day-1)
@register('TIME',3,family='Date and time')
def make_time(h,m,s):
    h,m,s=integer(h),integer(m),integer(s)
    if any(v<0 or v>32767 for v in (h,m,s)):raise ValueError('TIME arguments must be from 0 to 32767')
    return dt.datetime(1899,12,30)+dt.timedelta(seconds=(h*3600+m*60+s)%86400)
register('DATEVALUE',1,family='Date and time')(lambda x:date(x).replace(hour=0,minute=0,second=0,microsecond=0))
register('TIMEVALUE',1,family='Date and time')(lambda x:dt.datetime(1899,12,30)+dt.timedelta(hours=date(x).hour,minutes=date(x).minute,seconds=date(x).second))
for name,attr in [('YEAR','year'),('MONTH','month'),('DAY','day'),('HOUR','hour'),('MINUTE','minute'),('SECOND','second')]:
    register(name,1,family='Date and time')(lambda x,attr=attr:getattr(date(x),attr))
register('QUARTER',1,family='Date and time')(lambda x:(date(x).month-1)//3+1)
register('EDATE',2,family='Date and time')(lambda x,n:month_shift(x,n).replace(hour=0,minute=0,second=0,microsecond=0))
register('EOMONTH',2,family='Date and time')(lambda x,n:month_shift(x,round_dax(n),True).replace(hour=0,minute=0,second=0,microsecond=0))
register('NOW',0,family='Date and time')(lambda:dt.datetime.now())
register('TODAY',0,family='Date and time')(lambda:dt.datetime.combine(dt.date.today(),dt.time()))
register('UTCNOW',0,family='Date and time')(lambda:dt.datetime.now(dt.timezone.utc).replace(tzinfo=None))
register('UTCTODAY',0,family='Date and time')(lambda:dt.datetime.combine(dt.datetime.now(dt.timezone.utc).date(),dt.time()))
@register('WEEKDAY',1,2,'Date and time')
def weekday(value,return_type=1):
    d=date(value).weekday();t=integer(return_type)
    if t==1:return (d+1)%7+1
    if t==2:return d+1
    if t==3:return d
    raise ValueError('WEEKDAY supports return types 1, 2 and 3')
@register('WEEKNUM',1,2,'Date and time')
def weeknum(value,return_type=1):
    value=date(value);t=integer(return_type)
    if t==21:return value.isocalendar().week
    if t not in (1,2):raise ValueError('WEEKNUM supports return types 1, 2 and 21')
    first=dt.datetime(value.year,1,1);offset=(first.weekday()+(1 if t==1 else 0))%7
    return ((value-first).days+offset)//7+1
@register('DATEDIFF',3,family='Date and time')
def datediff(a,b,interval):
    a,b=date(a),date(b);unit=text(interval).upper()
    if unit=='YEAR':return b.year-a.year
    if unit=='QUARTER':return (b.year-a.year)*4+(b.month-1)//3-(a.month-1)//3
    if unit=='MONTH':return (b.year-a.year)*12+b.month-a.month
    if unit=='WEEK':
        # DAX counts Sunday boundaries.
        return ((b.date()-dt.date(1899,12,31)).days//7)-((a.date()-dt.date(1899,12,31)).days//7)
    seconds={'DAY':86400,'HOUR':3600,'MINUTE':60,'SECOND':1}.get(unit)
    if not seconds:raise ValueError('Unsupported DATEDIFF interval')
    origin=dt.datetime(1900,1,1)
    return math.floor((b-origin).total_seconds()/seconds)-math.floor((a-origin).total_seconds()/seconds)

# Standard annuity functions. Iterative financial solvers are deliberately separate.
def payment(rate,nper,pv,fv=0,kind=0):
    rate,nper,pv,fv=map(number,(rate,nper,pv,fv));kind=integer(kind)
    if kind not in (0,1) or nper==0:raise ValueError('Invalid annuity period/type')
    if not rate:return -(pv+fv)/nper
    growth=(1+rate)**nper
    return -(pv*growth+fv)*rate/((1+rate*kind)*(growth-1))
register('PMT',3,5,'Financial')(payment)
@register('FV',3,5,'Financial')
def fv(rate,nper,pmt,pv=0,kind=0):
    rate,nper,pmt,pv=map(number,(rate,nper,pmt,pv));kind=integer(kind)
    if kind not in (0,1):raise ValueError('Invalid payment type')
    if not rate:return -(pv+pmt*nper)
    growth=(1+rate)**nper
    return -(pv*growth+pmt*(1+rate*kind)*(growth-1)/rate)
@register('PV',3,5,'Financial')
def pv(rate,nper,pmt,future=0,kind=0):
    rate,nper,pmt,future=map(number,(rate,nper,pmt,future));kind=integer(kind)
    if kind not in (0,1):raise ValueError('Invalid payment type')
    if not rate:return -(future+pmt*nper)
    growth=(1+rate)**nper
    return -(future+pmt*(1+rate*kind)*(growth-1)/rate)/growth
@register('NPER',3,5,'Financial')
def nper(rate,pmt,pv,future=0,kind=0):
    rate,pmt,pv,future=map(number,(rate,pmt,pv,future));kind=integer(kind)
    if kind not in (0,1):raise ValueError('Invalid payment type')
    if not rate:return -(pv+future)/pmt
    payment=pmt*(1+rate*kind)/rate
    return math.log((payment-future)/(pv+payment))/math.log(1+rate)

# Parent-child path readers. PATH construction is handled with model rows.
register('PATHLENGTH',1,family='Parent and child')(lambda x:len(text(x).split('|')) if text(x) else None)
register('PATHCONTAINS',2,family='Parent and child')(lambda x,item:text(item) in text(x).split('|'))
@register('PATHITEM',2,3,'Parent and child')
def pathitem(path,position,kind=0):
    items=text(path).split('|');pos=integer(position);kind=integer(kind)
    if kind not in (0,1):raise ValueError('PATHITEM type must be TEXT/0 or INTEGER/1')
    if pos<1 or pos>len(items):return None
    return integer(items[pos-1]) if kind else items[pos-1]
register('PATHITEMREVERSE',2,3,'Parent and child')(lambda path,pos,kind=0:pathitem('|'.join(reversed(text(path).split('|'))),pos,kind))

@register('FORMAT',2,3,'Text')
def format_value(value,mask,locale='en-US'):
    """Common OLE numeric/date formats. Unimplemented masks raise an error."""
    if value is None:return ''
    from babel import Locale, UnknownLocaleError
    from babel.numbers import format_decimal, get_decimal_symbol, format_currency, get_territory_currencies
    from babel.dates import format_date, format_datetime, format_time, get_date_format
    try: culture=Locale.parse(str(locale or 'en-US').replace('-','_'))
    except (UnknownLocaleError,ValueError,TypeError) as error:
        raise ValueError('FORMAT does not recognize locale '+repr(locale)) from error
    mask=text(mask)
    if isinstance(value,(dt.date,dt.datetime)):
        original=value
        value=date(value)
        date_masks={'yyyy-mm-dd':'yyyy-MM-dd','mm/dd/yyyy':'MM/dd/yyyy','dd/mm/yyyy':'dd/MM/yyyy','yyyy':'yyyy','mmm yyyy':'MMM yyyy','mmmm yyyy':'MMMM yyyy','d':'d','mmmm':'MMMM','ddd, mmm d':'EEE, MMM d','mmm d':'MMM d','mmmm d':'MMMM d','d mmm yyyy':'d MMM yyyy'}
        if mask.lower() in date_masks:return format_date(value,date_masks[mask.lower()],locale=culture)
        if mask.lower()=='hh:nn:ss':return format_time(original if isinstance(original,dt.datetime) else dt.time(),format='HH:mm:ss',locale=culture)
        if mask.lower()=='short date':
            pattern=re.sub(r'(?<!y)y{1,2}(?!y)','yyyy',get_date_format('short',locale=culture).pattern)
            return format_date(value,pattern,locale=culture)
        if mask.lower() in ('general date',''):
            if culture.language=='en' and culture.territory=='US':return str(value.month)+'/'+str(value.day)+'/'+str(value.year)+' '+(original if isinstance(original,dt.datetime) else dt.datetime.combine(value,dt.time())).strftime('%I:%M:%S %p').lstrip('0')
            return format_datetime(original if isinstance(original,dt.datetime) else dt.datetime.combine(value,dt.time()),format='short',locale=culture)
        if mask.lower()=='long date':return format_date(value,format='full',locale=culture)
        tokens=re.findall(r'"[^"]*"|\\.|AM/PM|A/P|yyyy|yy|mmmm|mmm|mm|m|dddd|ddd|dd|d|hh|h|nn|n|ss|s|[^a-zA-Z"\\]+',mask,re.I)
        if ''.join(tokens)==mask and tokens:
            clock12=any(t.lower() in ('am/pm','a/p') for t in tokens)
            fields=[(i,t.lower()) for i,t in enumerate(tokens) if t[0].isalpha()]
            pattern=[]
            for i,token in enumerate(tokens):
                lower=token.lower()
                if token.startswith('"') or token.startswith('\\'):
                    literal=token[1:-1] if token.startswith('"') else token[1:]
                    pattern.append("'"+literal.replace("'","''")+"'");continue
                previous=next((t for j,t in reversed(fields) if j<i),'')
                following=next((t for j,t in fields if j>i),'')
                minute=lower in ('m','mm') and (previous in ('h','hh') or following in ('s','ss'))
                mapped={'yyyy':'yyyy','yy':'yy','mmmm':'MMMM','mmm':'MMM','mm':'mm' if minute else 'MM','m':'m' if minute else 'M','dddd':'EEEE','ddd':'EEE','dd':'dd','d':'d','hh':'hh' if clock12 else 'HH','h':'h' if clock12 else 'H','nn':'mm','n':'m','ss':'ss','s':'s','am/pm':'a','a/p':'aaaaa'}.get(lower,token)
                pattern.append(mapped)
            return format_datetime(value,''.join(pattern),locale=culture)
        raise ValueError('Unsupported FORMAT date mask: '+mask)
    v=number(value)
    named={'fixed':'0.00','standard':'#,##0.00','percent':'0.00%','currency':'$#,##0.00'}
    if mask.lower() in ('','general number'):return text(value).replace('.',get_decimal_symbol(culture))
    if mask.lower()=='scientific':return format(float(v),'.2E').replace('.',get_decimal_symbol(culture))
    if mask.lower()=='currency':
        currencies=get_territory_currencies(culture.territory) if culture.territory else []
        return format_currency(v,currencies[0] if currencies else 'USD',locale=culture)
    for label,pair in {'yes/no':('Yes','No'),'true/false':('True','False'),'on/off':('On','Off')}.items():
        if mask.lower()==label:return pair[0] if v else pair[1]
    mask=named.get(mask.lower(),mask)
    sections=mask.split(';')
    if len(sections)>3:raise ValueError('FORMAT supports at most three sections')
    chosen=sections[1] if v<0 and len(sections)>1 else sections[2] if v==0 and len(sections)>2 else sections[0]
    chosen=chosen or sections[0]
    if re.fullmatch(r'"[^";]*"',chosen):return chosen[1:-1]
    match=re.fullmatch(r'(?P<prefix>(?:"[^"]*"|\\.|[^#0.,;])*)(?P<whole>[#0]+(?:,[#0]+)*)(?P<scale>,*)(?:\.(?P<fraction>[#0]+))?(?P<postscale>,*)(?P<suffix>(?:"[^"]*"|\\.|[^#0.,;])*)',chosen)
    if not match:raise ValueError('Unsupported FORMAT numeric mask: '+chosen)
    fraction=match['fraction'] or '';digits=len(fraction)
    if digits>20:raise ValueError('FORMAT decimal precision exceeds limit')
    use_abs=v<0 and len(sections)>1
    scaled=Decimal(str(abs(v) if use_abs else v))
    # Commas adjacent to the numeric placeholders scale by powers of 1,000;
    # grouping commas inside the integer mask retain their original meaning.
    scaled/=Decimal(1000)**(len(match['scale'])+len(match['postscale']))
    def literal(part):
        return re.sub(r'"([^"]*)"|\\(.)',lambda m:m[1] if m[1] is not None else m[2],part)
    percent=re.sub(r'"[^"]*"|\\.','',match['prefix']+match['suffix'])
    if '%' in percent:scaled*=100
    rounded=Decimal(str(scaled)).quantize(Decimal(10)**-digits,rounding=ROUND_HALF_UP)
    whole=match['whole']
    if ',' in whole and whole.count('0')==1:whole='#,##0'
    pattern=whole+('.'+fraction if fraction else '')
    formatted=format_decimal(rounded,format=pattern,locale=culture,decimal_quantization=False)
    return literal(match['prefix'])+formatted+literal(match['suffix'])
