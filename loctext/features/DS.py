from nalaf.features.relations import EdgeFeatureGenerator
from nalaf.utils.graph import get_path, build_walks
from nalaf import print_debug
from nltk.stem import PorterStemmer
from loctext.util import PRO_ID, LOC_ID, REL_PRO_LOC_ID


def is_POS_Noun(token):
    """ matches NN, NNS, NNP, NNPS : https://www.ling.upenn.edu/courses/Fall_2003/ling001/penn_treebank_pos.html"""
    return "NN" == token.features['pos'][0:2]


def is_POS_Verb(token):
    return "V" == token.features['pos'][0]


def get_tokens_within(sentence, token_1, token_2):
    assert token_1.start < token_2.start, \
        "The tokens must be sorted as such: t1 ({}:{}) < t2 ({}:{})".format(token_1.start, token_1.word, token_2.start, token_2.word)

    if 'id' in token_1.features:
        # That is, tokens have feature 'id' (Parser.py), which indicates the token index in the sentence
        t1_index_plus_1 = token_1.features['id'] + 1   # + 1, first, because we do not want to include the token itself
        t2_index = token_2.features['id']

        ret = (sentence[i] for i in range(t1_index_plus_1, t2_index))

        return ret

    else:
        raise Exception("Not implemented")


def combine_sentences(edge, sentence1, sentence2):
    """
    Combine two simple simple normal sentences into a "chained" sentence with
    dependecies and paths created as necessary for the DS model.

    `createCombinedSentence` re-implementation of Shrikant's (java) into Python.

    Each sentence is a list of Tokens as defined in class Part (nalaf: data.py).

    The sentences are assumed, but not asserted, to be different and sorted:
    sentence1 must be before sentence2.
    """

    combined_sentence = sentence1 + sentence2

    combined_sentence = _add_extra_links(edge, combined_sentence, sentence1, sentence2)

    return combined_sentence


def get_sentence_roots(sentence, feature_key='is_root'):
    """
    See parsers.py :: SpacyParser.
    """
    roots = [token for token in sentence if token.features[feature_key] is True]
    assert len(roots) >= 1, "The sentence contains {} roots (?). Expected: >= 1 -- Sentence: {}".format(len(roots), ' '.join((t.word for t in sentence)))

    return roots


def _add_extra_links(edge, combined_sentence, sentence1, sentence2):
    """
    `addExtraLinks` re-implementation of Shrikant's (java) into Python.

    Some comments and commented-out code exactly as original java code.
    """

    _addWordSimilarityLinks(combined_sentence, sentence1, sentence2)

    # TODO would be better to not use the constants PRO_ID (protRef) and LOC_ID (locRef) (below) here -- It's hardcoded
    _addEntityLinks(edge, combined_sentence, sentence1, sentence2, PRO_ID, ['protein'], "protRef")

    # Just as we added the links from "protein" to actual protein entities
    # add the links from "location"/"localization" to location entity
    _addEntityLinks(edge, combined_sentence, sentence1, sentence2, LOC_ID, ['location', 'localiz', 'compartment'], "locRef")

    # addProteinFamilyLinks(combSentence, tokenOffset);

    _addRootLinks(combined_sentence, sentence1, sentence2)

    # addShortFormLinks(combSentence, prevSentence, currSentence)

    return combined_sentence


def _addWordSimilarityLinks(combined_sentence, sentence1, sentence2):
    """
    add links between words (nouns) that have same tokenText in prev & currSentence
    """
    from itertools import product

    for (s1_token, s2_token) in product(sentence1, sentence2):

        if is_POS_Noun(s1_token) and is_POS_Noun(s2_token):

            if s1_token.word == s2_token.word:
                s1_token.features['user_dependency_to'].append((s2_token, "wordSim"))
                s2_token.features['user_dependency_from'].append((s1_token, "wordSim"))

            # TODO note, here I'm using the (spacy) lemma, not the (Porter) stem
            if s1_token.features['lemma'] == s2_token.features['lemma']:
                s1_token.features['user_dependency_to'].append((s2_token, "stemSim"))
                s2_token.features['user_dependency_from'].append((s1_token, "stemSim"))


def _addEntityLinks(edge, combined_sentence, sentence1, sentence2, class_id, key_words, dependency_type):
    """
    `addProteinLinks` and `addLocationLinks` re-implementation of Shrikant's (java) into Python.
    """

    assert edge.same_part

    def _do_one_direction(sent_a, sent_b):

        sent_a_contains_entity = edge.entity1.class_id == class_id
        if not sent_a_contains_entity:
            sent_a_tokens_that_match_key_words = (t for t in sent_a if any(kw in t.word.lower() for kw in key_words))

            for sent_a_token in sent_a_tokens_that_match_key_words:

                for sent_b_token in sent_b:

                    sent_b_token_in_entity = sent_b_token.get_entity(edge.same_part)
                    if sent_b_token_in_entity is not None and sent_b_token_in_entity.class_id == class_id:

                        sent_a_token.features['user_dependency_to'].append((sent_b_token, dependency_type))
                        sent_b_token.features['user_dependency_from'].append((sent_a_token, dependency_type))

    # In combination: do both directions
    _do_one_direction(sentence1, sentence2)
    _do_one_direction(sentence2, sentence1)


def _addRootLinks(combined_sentence, sentence1, sentence2):
    """
    link roots of both the sentences

    `addRootLinks` re-implementation of Shrikant's (java) into Python.


    *IMPORTANT*:

    * Shrikant/Java/CoreNLP code had one single root for every sentence
    * Python/spaCy sentences can have more than 1 root
    * --> Therefore, we create a product of links of all the roots
    * --> see: (https://github.com/juanmirocks/LocText/issues/6#issue-177139892)


    Dependency directions:

    sentence1 -> sentence2
    sentence2 <- sentence1
    """
    from itertools import product

    for (s1_root, s2_root) in product(get_sentence_roots(sentence1), get_sentence_roots(sentence2)):

        s1_root.features['user_dependency_to'].append((s2_root, "rootDepForward"))
        s1_root.features['user_dependency_from'].append((s2_root, "rootDepBackward"))

        s2_root.features['user_dependency_from'].append((s1_root, "rootDepForward"))
        s2_root.features['user_dependency_to'].append((s1_root, "rootDepBackward"))


class AnyNGramFeatureGenerator(EdgeFeatureGenerator):
    """
    `buildBigramFeatures` and `buildTrigramFeature` all-in-one re-implementation of Shrikant's (java) into Python.
    """

    def __init__(
        self,
        n_gram,
        prefix_bow=None,
        prefix_bow_masked=None,
        prefix_pos=None,
        prefix_stem=None
    ):

        self.n_gram = n_gram

        self.prefix_bow = prefix_bow
        self.prefix_bow_masked = prefix_bow_masked
        self.prefix_pos = prefix_pos
        self.prefix_stem = prefix_stem

        self.stemmer = PorterStemmer()
        """an instance of the PorterStemmer"""

        self.features = [
            ("prefix_bow", lambda tok, _: tok.word),  # TODO should it be lowercase ???
            ("prefix_bow_masked", lambda tok, edge: tok.masked_text(edge.same_part)),
            ("prefix_pos", lambda tok, _: tok.features['pos']),
            ("prefix_stem", lambda tok, _: self.stemmer.stem(tok.word))
        ]


    def generate(self, dataset, feature_set, is_training_mode):

        for edge in dataset.edges():
            (sentence1, sentence2) = edge.get_sentences_pair(force_sort=True)
            combined_sentence = combine_sentences(edge, sentence1, sentence2)

            n_grams = zip(*(combined_sentence[start:] for start in range(0, self.n_gram)))

            for tokens in n_grams:

                for feature_pair in self.features:
                    transformed_tokens = (feature_pair[1](t, edge) for t in tokens)

                    feature_name = self.gen_prefix_feat_name(feature_pair[0], str(self.n_gram)+"-gram", *transformed_tokens)
                    self.add_to_feature_set(feature_set, is_training_mode, edge, feature_name)


class PatternFeatureGenerator(EdgeFeatureGenerator):
    """
    `buildPatternFeature` re-implementation of Shrikant's (java) into Python.
    """

    def __init__(
        self,
        e1_class,
        e2_class,
        prefix_ProtVerbWord=None,
        prefix_WordVerbProt=None,
        prefix_LocVerbWord=None,
        prefix_WordVerbLoc=None,
        prefix_ProtVerbWordLocVerbWord=None,
        prefix_ProtVerbWordVerbLoc=None,
        prefix_WordVerbProtLocVerbWord=None,
        prefix_WordVerbProtWordVerbLoc=None,
    ):
        self.e1_class = e1_class
        self.e2_class = e2_class

        self.prefix_ProtVerbWord = prefix_ProtVerbWord
        self.prefix_WordVerbProt = prefix_WordVerbProt
        self.prefix_LocVerbWord = prefix_LocVerbWord
        self.prefix_WordVerbLoc = prefix_WordVerbLoc
        self.prefix_ProtVerbWordLocVerbWord = prefix_ProtVerbWordLocVerbWord
        self.prefix_ProtVerbWordVerbLoc = prefix_ProtVerbWordVerbLoc
        self.prefix_WordVerbProtLocVerbWord = prefix_WordVerbProtLocVerbWord
        self.prefix_WordVerbProtWordVerbLoc = prefix_WordVerbProtWordVerbLoc


    def generate(self, dataset, feature_set, is_training_mode):
        from itertools import product

        # ---

        def exist_verb_token_within(sentence, token1, token2):
            return any(is_POS_Verb(t) for t in get_tokens_within(sentence, token1, token2))

        def add_simple_binary_feature(prefix_name):
            feature_name = self.gen_prefix_feat_name(prefix_name)
            self.add_to_feature_set(feature_set, is_training_mode, edge, feature_name)

        # ---

        for edge in dataset.edges():
            s1, s2 = edge.get_sentences_pair(force_sort=False)
            e1, e2 = edge.entity1, edge.entity2

            is_prot_in_s1 = e1.class_id == self.e1_class
            if is_prot_in_s1:  # protein in first sentence and localization in second
                assert e2.class_id == self.e2_class
            else:  # location in first sentence and protein in second
                assert e2.class_id == self.e1_class
                # Swap: put in (logically) the protein in the first sentence to simplify code later
                s1, s2 = s2, s1
                e1, e2 = e2, e1

            # Pattern, e.g. first: (protein token) then (token verb) then (some token that matches in other sentence)
            protVerbWord = False
            wordVerbProt = False
            locVerbWord = False
            wordVerbLoc = False

            for (s1_t1, s2_t2) in product(s1, s2):

                if (is_POS_Noun(s1_t1) and
                    # ⚠️ Note, I (Juanmi) decide to and compare in lower case. Shrikant's was code sensitive
                    s1_t1.word.lower() == s2_t2.word.lower() and

                    # ⚠️ Shrikant uses the **head token** of an entity (i.e. not necessarily the first token)
                    # ⚠️ I (Juanmi) use the first token and, instead of checking that s1_t1 is not an entity
                    s1_t1.get_entity(edge.same_part) is None and
                    # ⚠️ the following clause was not in Shrikant's code
                    s2_t2.get_entity(edge.same_part) is None and
                    # ⚠️ Note that entities can be within tokens, e.g. example_[P53], or or spand multiple ones, e.g. [cell surface]
                    # that also means that entity.offset is not necessarily == entity.tokens.start
                    s1_t1.start != e1.tokens[0].start and s2_t2.start != e2.tokens[0].start):

                    if e1.tokens[0].start < s1_t1.start:
                        if exist_verb_token_within(s1, e1.tokens[0], s1_t1):
                            protVerbWord = True
                    else:
                        if exist_verb_token_within(s1, s1_t1, e1.tokens[0]):
                            wordVerbProt = True

                    if e2.tokens[0].start < s2_t2.start:
                        if exist_verb_token_within(s2, e2.tokens[0], s2_t2):
                            locVerbWord = True
                    else:
                        if exist_verb_token_within(s2, s2_t2, e2.tokens[0]):
                            wordVerbLoc = True

            if protVerbWord:
                add_simple_binary_feature('prefix_ProtVerbWord')
            if wordVerbProt:
                add_simple_binary_feature('prefix_WordVerbProt')
            if locVerbWord:
                add_simple_binary_feature('prefix_LocVerbWord')
            if wordVerbLoc:
                add_simple_binary_feature('prefix_WordVerbLoc')
            if protVerbWord and locVerbWord:
                add_simple_binary_feature('prefix_ProtVerbWordLocVerbWord')
            if protVerbWord and wordVerbLoc:
                add_simple_binary_feature('prefix_ProtVerbWordVerbLoc')
            if wordVerbProt and locVerbWord:
                add_simple_binary_feature('prefix_WordVerbProtLocVerbWord')
            if wordVerbProt and wordVerbLoc:
                add_simple_binary_feature('prefix_WordVerbProtWordVerbLoc')


class SameWordFeatureGenerator(EdgeFeatureGenerator):
    """
    `buildSameWordFeature` re-implementation of Shrikant's (java) into Python.
    """

    def __init__(
        self,
        # e1_class,
        # e2_class,
        prefix_sameWords=None,
        prefix_sameWordsSamePOS=None,
        prefix_sameStem=None,
        prefix_sameStemSamePOS=None,
    ):

        self.prefix_sameWords = prefix_sameWords
        self.prefix_sameWordsSamePOS = prefix_sameWordsSamePOS
        self.prefix_sameStem = prefix_sameStem
        self.prefix_sameStemSamePOS = prefix_sameStemSamePOS


    def generate(self, dataset, feature_set, is_training_mode):

        for edge in dataset.edges():

            s1, s2 = edge.get_sentences_pair(force_sort=False)

            for t1 in s1:
                for t2 in s2:
                    t1_POS = t1.features['pos']
                    t2_POS = t2.features['pos']

                    # ⚠️ newly, I compare in lower case thus ignoring the case (different than Shrikant's)
                    if t1.word.lower() == t2.word.lower():
                        self.gen_preffeatname_add(feature_set, is_training_mode, edge, "prefix_sameWords", t1.word.lower())

                        if t1_POS == t2_POS:
                            self.gen_preffeatname_add(feature_set, is_training_mode, edge, "prefix_sameWordsSamePOS", t1.word.lower(), t1_POS)

                    # ⚠️ note, here I'm using the (spacy) lemma, not the (Porter) stem as in Shrikant's
                    if t1.features['lemma'] == t2.features['lemma']:
                        self.gen_preffeatname_add(feature_set, is_training_mode, edge, "prefix_sameStem", t1.features['lemma'])

                        if t1_POS == t2_POS:
                            self.gen_preffeatname_add(feature_set, is_training_mode, edge, "prefix_sameStemSamePOS", t1.features['lemma'], t1_POS)
