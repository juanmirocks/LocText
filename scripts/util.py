import matplotlib.pyplot as plot
import sklearn
from sklearn.svm import SVC
from sklearn.model_selection import StratifiedKFold
from sklearn.feature_selection import RFECV
from sklearn.datasets import make_classification
from sklearn.datasets import load_iris
from sklearn.feature_selection import SelectKBest
from sklearn.feature_selection import mutual_info_classif
from sklearn.metrics import fbeta_score, make_scorer
import numpy as np
import scipy
import time

from nalaf.structures.data import Dataset
from nalaf.learning.lib.sklsvm import SklSVM
from nalaf.structures.data import Dataset
from loctext.learning.train import read_corpus
from loctext.util import PRO_ID, LOC_ID, ORG_ID, REL_PRO_LOC_ID, UNIPROT_NORM_ID, GO_NORM_ID, TAXONOMY_NORM_ID
from loctext.learning.annotators import StringTagger
from loctext.learning.annotators import LocTextDXModelRelationExtractor
from loctext.util import *
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.utils.validation import check_X_y, check_array, check_is_fitted
from sklearn.utils.multiclass import unique_labels
from sklearn.metrics import euclidean_distances
from sklearn.preprocessing import FunctionTransformer, maxabs_scale


F05_SCORER = make_scorer(fbeta_score, beta=0.5)  # Assigns double the weight to *precision*
F025_SCORER = make_scorer(fbeta_score, beta=0.25)  # Assigns quadruple the weight to *precision*


def get_model_and_data(sentence_distance, predict_entities):
    corpus = read_corpus("LocText", predict_entities=predict_entities)

    # TODO the specific parameters like C=1 or even `linear` are controversial -- Maybe I should I change that
    annotator = LocTextDXModelRelationExtractor(PRO_ID, LOC_ID, REL_PRO_LOC_ID, sentence_distance, use_predicted_entities=len(predict_entities) > 0, preprocess=True, kernel='linear', C=1)
    annotator.pipeline.execute(corpus)
    X, y, groups = annotator.model.write_vector_instances(corpus, annotator.pipeline.feature_set)
    X = annotator.model.preprocess.fit_transform(X)

    return (annotator, X, y, groups)


def my_cv_generator(groups, num_instances=None):
    if num_instances is not None:
        assert(num_instances == sum(len(v) for v in groups.values()))

    def map_indexes(doc_keys):
        # Convert document keys to the final instances indexes
        ret = [instance_index for doc_key in doc_keys for instance_index in groups[doc_key]]
        assert(len(ret) == len(set(ret)))
        return ret

    k = 5
    for training_docs_keys, evaluation_doc_keys in Dataset._cv_kfold_splits_doc_keys_sets(groups.keys(), k, validation_set=True):
        tr, ev = map_indexes(training_docs_keys), map_indexes(evaluation_doc_keys)
        yield tr, ev


def plot_recursive_features(scoring_name, scores, save_to=None, show=False):
    fig = plot.figure()
    plot.xlabel("Number of features selected")
    plot.ylabel("{}".format(scoring_name.upper()))
    plot.plot(range(1, len(scores) + 1), scores)

    if save_to:
        fig.savefig(save_to)

    if show:
        plot.show()

    return fig


def get_sorted_kbest_feature_keys(kbest_fitted_model):
    return [fkey for fkey, _ in sorted(enumerate(kbest_fitted_model.scores_), key=lambda tuple: tuple[1], reverse=True)]


def select_features_transformer_function(X, **kwargs):
    selected_feature_keys = kwargs["selected_feature_keys"]

    X_new = X[:, selected_feature_keys]

    return X_new


def select_features_transformer(selected_feature_keys):
    return FunctionTransformer(select_features_transformer_function, accept_sparse=True, kw_args={"selected_feature_keys": selected_feature_keys})


class KBestSVC(BaseEstimator, ClassifierMixin):  # TODO inheriting on these ones makes any change?

    def __init__(self, X_whole, y_whole, score_func, k=None):
        self.X_whole = X_whole
        self.y_whole = y_whole

        self.score_func = score_func
        self.k = k
        self.kbest = None
        self.kbest_unfitted = True

        self.svc = SVC(kernel='linear', C=1, verbose=False)  # TODO C=1 linear / rbf ??

    def fit(self, X, y):
        if self.kbest_unfitted:
            self.kbest = SelectKBest(score_func=self.score_func, k=self.k)
            self.kbest.fit(self.X_whole, self.y_whole)
            self.kbest_unfitted = False

        X_new = self.kbest.transform(X)

        return self.svc.fit(X_new, y)

    def predict(self, X):
        X_new = self.kbest.transform(X)

        return self.svc.predict(X_new)
