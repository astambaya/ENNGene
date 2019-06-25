from ..utils import file_utils as f
from ..utils import sequence as seq


class Dataset:

    def __init__(self, branch, klass=None, bed_file=None, ref_dict=None, strand=None, encoding=None, datasetlist=None):
        self.branch = branch

        if datasetlist:
            self.dictionary = self.merge(datasetlist)
        else:
            # TODO is there a way a folding branch could use already converted datasets from seq branch, if available?
            # TODO complementarity currently applied only to sequence. Does the conservation score depend on strand?
            complement = branch == 'seq' or branch == 'fold'
            self.dictionary = self.bed_to_dictionary(bed_file, ref_dict, strand, klass, complement)

            if self.branch == 'fold' and not datasetlist:
                # can the result really be a dictionary? probably should
                file_name = branch + "_" + klass
                self.dictionary = seq.fold(self.dictionary, file_name)

            # TODO apply one-hot encoding also to the fold branch? 
            if encoding and branch == 'seq':
                for key, arr in self.dictionary.items():
                    new_arr = [seq.translate(item, encoding) for item in arr]
                    self.dictionary.update({key: new_arr})

    # TODO allow random separation too
    # TODO do not call per category, it iterates over the same data multiple times
    # instead call it once and separate it to all the given categories
    def separate_by_chr(self, chr_list):
        separated_dataset = {}
        for key, sequence_list in self.dictionary.items():
            chromosome = key.split('_')[0]
            if chromosome in chr_list:
                separated_dataset.update({key: sequence_list})

        return separated_dataset

    # def export_to_bed(self, path):
    #     return f.dictionary_to_bed(self.dictionary, path)
    #
    # def export_to_fasta(self, path):
    #     return f.dictionary_to_fasta(self.dictionary, path)

    @staticmethod
    def bed_to_dictionary(bed_file, ref_dictionary, strand, klass, complement):
        file = f.filehandle_for(bed_file)
        final_dict = {}

        for line in file:
            values = line.split()

            chrom_name = values[0]
            seq_start = values[1]
            seq_end = values[2]
            strand_sign = None
            sequence = None

            # TODO implement as a standalone object with attributes chrom_name, seq_start, ...
            try:
                strand_sign = values[5]
                key = chrom_name + "_" + seq_start + "_" + seq_end + "_" + strand_sign + '_' + klass
            except:
                key = chrom_name + "_" + seq_start + "_" + seq_end + '_' + klass

            if chrom_name in ref_dictionary.keys():
                # first position in chromosome in bed file is assigned as 0 (thus it fits the python indexing from 0)
                start_position = int(seq_start)
                # both bed file coordinates and python range exclude the last position
                end_position = int(seq_end)
                sequence = []
                for i in range(start_position, end_position):
                    sequence.append(ref_dictionary[chrom_name][i])

                if complement and strand and strand_sign == '-':
                    sequence = seq.complement(sequence, seq.DNA_COMPLEMENTARY)

            if key and sequence:
                final_dict.update({key: sequence})

        return final_dict

    @staticmethod
    def merge(list_of_datasets):
        merged_dictionary = {}
        for dataset in list_of_datasets:
            merged_dictionary.update(dataset.dictionary)

        return merged_dictionary
