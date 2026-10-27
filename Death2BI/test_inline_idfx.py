import struct
import unittest
from types import SimpleNamespace

from pbixray.abf.data_model import DataModel
from pbixray.vertipaq_decoder import VertiPaqDecoder
from semantic_model import configure_storage_decoder


def segment(values, *, metadata_records=None, statistics_records=None):
    """Small exact RLE segment using the existing documented IDF/CP tags."""
    records=sum(repeat for value,repeat in values)
    declared=records if metadata_records is None else metadata_records
    statistics=declared if statistics_records is None else statistics_records
    data=struct.pack('<Q',len(values))+b''.join(struct.pack('<II',*pair) for pair in values)+struct.pack('<Q',0)
    stats=(b'<1:SS\0'+struct.pack('<QIIIqQBQQ',len({value for value,_ in values}),
           min((value for value,_ in values),default=3),max((value for value,_ in values),default=3),3,-1,statistics,0,len(values),0)+b'SS:1>\0')
    meta=(b'<1:CS\0'+struct.pack('<QQIII',declared,0,703031,0,3)+stats+b'\0CS:1>\0')
    return data,meta


def combined(*parts):
    payload=b''.join(data for data,meta in parts)
    metadata=b'<1:CP\0'+struct.pack('<Q',len(parts))+b''.join(meta for data,meta in parts)+b'CP:1>\0'
    return payload+metadata+struct.pack('<Q',len(metadata))


def model_for(files):
    data=b'';log=[]
    for name,content in files.items():
        log.append({'FileName':name,'m_cbOffsetHeader':len(data),'Size':len(content)})
        data+=content
    storage=DataModel(log,data)
    class Metadata:
        def __init__(self):self.calls=[]
        def get_segment_meta(self,column,idf=None):
            self.calls.append((column,idf));return [{'legacy':True}]
    source=Metadata();decoder=VertiPaqDecoder(source,storage)
    return SimpleNamespace(_data_model=storage,_metadata=SimpleNamespace(source=source),_vertipaq_decoder=decoder)


class InlineIdfxTests(unittest.TestCase):
    def test_exact_payload_and_metadata_multiple_segments_and_partitions(self):
        a=combined(segment([(3,2),(4,1)]),segment([(2,1),(7,2)]))
        b=combined(segment([(8,1)]))
        model=model_for({'a.idfx':a,'b.idfx':b});configure_storage_decoder(model)
        source=model._metadata.source;decoder=model._vertipaq_decoder
        for filename,raw,expected in [('a.idfx',a,[3,3,4,2,7,7]),('b.idfx',b,[8])]:
            metadata=source.get_segment_meta({'IDF':filename},filename)
            self.assertEqual(sum(part['records'] for part in metadata),len(expected))
            parsed=decoder._parse_idf(raw)
            self.assertEqual(len(parsed.segments),len(metadata))
            self.assertEqual(decoder._read_rle_bit_packed_hybrid(raw,metadata).tolist(),expected)
        self.assertEqual(source.calls,[])
        metadata=source.get_segment_meta({'IDF':'a.idfx'});metadata[0]['records']=999
        self.assertEqual(source.get_segment_meta({'IDF':'a.idfx'})[0]['records'],3)

    def test_ordinary_companion_metadata_and_other_models_remain_untouched(self):
        normal=segment([(3,1)])[0]
        model=model_for({'inline.idfx':combined(segment([(4,1)])),'ordinary.idf':normal,
                         'ordinary.idfmeta':b'existing','companion.idfx':normal,'companion.idfxmeta':b'existing'})
        other=model_for({'inline.idfx':combined(segment([(5,1)]))})
        original=other._vertipaq_decoder._parse_idf
        configure_storage_decoder(model)
        for name in ['ordinary.idf','companion.idfx']:
            self.assertEqual(model._metadata.source.get_segment_meta({'IDF':name}),[{'legacy':True}])
            self.assertEqual(model._vertipaq_decoder._parse_idf(normal).segments[0].primary_segment[0].data_value,3)
        self.assertEqual(len(model._metadata.source.calls),2)
        self.assertEqual(other._vertipaq_decoder._parse_idf,original)
        self.assertFalse(getattr(other._vertipaq_decoder,'_death2bi_storage',False))
        first=model._vertipaq_decoder._parse_idf;configure_storage_decoder(model)
        self.assertIs(model._vertipaq_decoder._parse_idf,first,'configuration is idempotent')

    def test_suffix_required_and_footer_is_not_discovered_by_scanning(self):
        raw=combined(segment([(3,1)]))
        model=model_for({'trigger.idfx':raw,'ordinary.idf':raw});configure_storage_decoder(model)
        self.assertEqual(model._metadata.source.get_segment_meta({'IDF':'ordinary.idf'}),[{'legacy':True}])
        corrupted=raw[:-8]+struct.pack('<Q',len(raw)+1)
        invalid=model_for({'bad.idfx':corrupted});configure_storage_decoder(invalid)
        with self.assertRaisesRegex(ValueError,'metadata length is outside'):
            invalid._metadata.source.get_segment_meta({'IDF':'bad.idfx'})

    def test_malformed_signature_trailing_bytes_and_segment_counts_fail_fast(self):
        raw=combined(segment([(3,2)]));length=struct.unpack('<Q',raw[-8:])[0];start=len(raw)-8-length
        cases={
            'signature':(raw[:start]+b'BAD CP'+raw[start+6:],'CP signature'),
            'extra-data':(raw[:start]+b'\0'+raw[start:],'segment counts disagree'),
            'rows':(combined(segment([(3,2)],metadata_records=3)),'data row count'),
            'statistics':(combined(segment([(3,2)],statistics_records=3)),'record counts disagree'),
            'primary-size':(struct.pack('<Q',2**64-1)+raw[8:],'primary segment exceeds'),
            'metadata-count':(raw[:start+6]+struct.pack('<Q',2**64-1)+raw[start+14:],'segment count is outside'),
        }
        for name,(content,message) in cases.items():
            with self.subTest(name=name):
                model=model_for({name+'.idfx':content});configure_storage_decoder(model)
                with self.assertRaisesRegex(ValueError,message):
                    model._metadata.source.get_segment_meta({'IDF':name+'.idfx'})

    def test_empty_inline_domain_keeps_zero_rows(self):
        raw=combined();model=model_for({'empty.idfx':raw});configure_storage_decoder(model)
        self.assertEqual(model._metadata.source.get_segment_meta({'IDF':'empty.idfx'}),[])
        self.assertEqual(model._vertipaq_decoder._parse_idf(raw).segments,[])


if __name__=='__main__':unittest.main()
