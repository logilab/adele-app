import unittest
import lxml.etree as ET
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import create_session
from sqlalchemy import create_engine


DB_URL="/Users/mrgecko/Documents/Dev/Data/adele/adele.sqlite"

DOC_ID = 20
DOC_FILEPATH = "/Users/mrgecko/Documents/Dev/Data/adele/dossiers/{0}.xml".format(DOC_ID)
NS_TI = {"ti": "http://www.tei-c.org/ns/1.0"}


class TestTranscriptionTranslationAlignment(unittest.TestCase):

    ALIGNMENT_STMT = """
    -- Transcription vs Translation
    SELECT
      transcription.transcription_id,
      translation.translation_id,
      substr(transcription.content, ptr_transcription_start, 
        ptr_transcription_end - ptr_transcription_start) as transcription,
      substr(translation.content, ptr_translation_start, 
        ptr_translation_end - ptr_translation_start) as translation
    FROM
      transcription
      JOIN alignment_translation
        on transcription.transcription_id = alignment_translation.transcription_id
      JOIN  translation
        ON alignment_translation.translation_id = translation.translation_id
    WHERE
      transcription.doc_id = {doc_id} 
      and 
      translation.doc_id = {doc_id}
    ;
    """.format(doc_id=DOC_ID)

    def setUp(self):
        self.doc = ET.parse(DOC_FILEPATH)
        self.engine = create_engine("sqlite:///{url}".format(url=DB_URL))

        def name_for_collection_relationship(base, local_cls, referred_cls, constraint):
            disc = '_'.join(col.name for col in constraint.columns)
            return referred_cls.__name__.lower() + '_' + disc + "_collection"
        automap_base().prepare(self.engine, reflect=True,
                               name_for_collection_relationship=name_for_collection_relationship)

        self.session = create_session(bind=self.engine)

        self.res = self.engine.execute(TestTranscriptionTranslationAlignment.ALIGNMENT_STMT).fetchall()

    def test_both_ids_match(self):
        # expect consistency between translation and traduction ids (shouldn't happen)
        transcription_ids = set()
        translation_ids = set()
        for (transcription_id, translation_id, a, b) in self.res:
            transcription_ids.add(transcription_id)
            translation_ids.add(translation_id)
        self.assertSetEqual(transcription_ids, translation_ids, "Something is wrong with the IDs")

    def test_alignment_is_correct(self):
        with open("./data/transcription_doc20.txt", "r") as transcription_f, \
             open("./data/translation_doc20.txt", "r") as translation_f:
            transcription_lines = transcription_f.read().splitlines()
            translation_lines = translation_f.read().splitlines()

            for i, transcription in enumerate(transcription_lines):
                translation = translation_lines[i]

                self.assertEqual(self.res[i]["transcription"], transcription, "Transcription ptrs look wrong")
                self.assertEqual(self.res[i]["translation"], translation, "Translation ptrs look wrong")


if __name__ == '__main__':
    unittest.main()
