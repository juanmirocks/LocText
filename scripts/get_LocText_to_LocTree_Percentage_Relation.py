import re
import json

loctree_records_file_path = "../resources/features/9606_Homo_sapiens_LocTree_relations.tsv"
loctext_records_file_path = "../resources/features/9606_NewDiscoveries_relations.tsv"
output_file_path = "../resources/features/"
output_file_name = "9606_positive_relations.json"
regex_go_id = re.compile('GO:[0-9]+')


def get_loctree_relation_records(file_path=loctree_records_file_path):
    with open(file_path) as f:
        next(f)
        relations = {}

        # A record from LocTree is shown below
        # sp|P48200|IREB2_HUMAN	100	cytoplasm	cytoplasm GO:0005737(NAS); cytosol GO:0005829(IEA); mitochondrion GO:0005739(IEA);
        for line in f:

            protein_id, score, localization, gene_ontology_terms = line.split("\t")

            protein_id = protein_id[3:9]
            go_terms = regex_go_id.findall(gene_ontology_terms)
            relations[protein_id] = set(go_terms)

        return relations


def get_loctext_relation_records(loctree_relations, file_path=loctext_records_file_path):
    with open(file_path) as f:
        next(f)
        positive_relations = {}
        negative_relations = {}
        positives = 0
        negatives = 0
        # A record from LocText is shown below with column numbers
        #     0        1        2           3         4       5    6    7       8
        # RELATION	Q9H869	GO:0005737	cytoplasm	True	True		8	27979971
        for line in f:
            record = line.split("\t")

            if record[4] == 'False':
                loctext_uniprot_id = record[1]
                loctext_go_id = record[2]
                go_terms = loctree_relations.get(loctext_uniprot_id, {})
                if loctext_go_id in go_terms:
                    positive_relations[loctext_uniprot_id] = loctext_go_id
                    positives += 1
                else:
                    negative_relations[loctext_uniprot_id] = loctext_go_id
                    negatives += 1

        return positive_relations, negative_relations, positives, negatives+positives


if __name__ == "__main__":

    loctree_relations = get_loctree_relation_records()
    positive_relations, negative_relations, positiveRecords, totalRecords = get_loctext_relation_records(loctree_relations)

    print("***************************************************************************************************")
    print("LocText predicted RELATION ['in SwissProt' set to False], but present in SwissProt: ", positiveRecords)
    print("Total predicted RELATION ['in SwissProt' set to False]: ", totalRecords)
    print("Percentage predicts of LocText to LocTree: ", positiveRecords/totalRecords*100)
    print("positive_relations (present in SwissProt): ", len(positive_relations))
    print("negative_relations (absent in SwissProt): ", len(negative_relations))
    print("***************************************************************************************************")

    with open(output_file_path + "/" + output_file_name, "w") as output_file:
        json.dump(positive_relations, output_file)
