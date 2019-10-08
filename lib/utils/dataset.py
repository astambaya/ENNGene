import logging
import numpy as np
import os
import platform
import random
import subprocess
import tempfile

from zipfile import ZipFile, ZIP_DEFLATED

from .data_point import DataPoint
from . import file_utils as f
from . import sequence as seq

logger = logging.getLogger('main')


class Dataset:

    @classmethod
    def load_from_file(cls, file_path):
        if '.zip' in file_path:
            zipped = True
            archive = ZipFile(file_path, 'r')
            name = os.path.basename(file_path).replace('.zip', '')
            file = archive.open(name)
        else:
            zipped = False
            file = open(file_path, 'r')

        head = f.read_decoded_line(file, zipped)
        branches = head.split("\t")[1:]
        category = os.path.basename(file_path).replace('.zip', '')

        datapoint_list = []
        for line in file:
            if zipped:
                line = line.decode('utf-8')
            key, *values = line.strip().split("\t")
            branches_string_values = {}
            for i, value in enumerate(values):
                branches_string_values.update({branches[i]: value})
            datapoint_list.append(DataPoint.load(key, branches_string_values))

        return cls(branches=branches, category=category, datapoint_list=datapoint_list)

    @classmethod
    def split_by_chr(cls, dataset, chrs_by_category):
        categories_by_chr = cls.reverse_chrs_dictionary(chrs_by_category)

        # separate original dictionary by categories
        split_sets = {}
        for datapoint in dataset.datapoint_list:
            category = categories_by_chr[datapoint.chrom_name]
            if category not in split_sets.keys(): split_sets.update({category: []})
            split_sets[category].append(datapoint)

        # create Dataset objects from separated dictionaries
        final_datasets = set()
        for category, dp_list in split_sets.items():
            final_datasets.add(
                Dataset(klass=dataset.klass, branches=dataset.branches, category=category, datapoint_list=dp_list))

        return final_datasets

    @classmethod
    def reverse_chrs_dictionary(cls, dictionary):
        reversed_dict = {}
        for key, chrs in dictionary.items():
            for chr in chrs:
                reversed_dict.update({chr: key})

        return reversed_dict

    @classmethod
    def split_random(cls, dataset, ratio_list, seed):
        # so far the categories are fixed, not sure if there would be need for custom categories
        categories_ratio = {'train': float(ratio_list[0]),
                            'validation': float(ratio_list[1]),
                            'test': float(ratio_list[2]),
                            'blackbox': float(ratio_list[3])}

        random.seed(seed)
        random.shuffle(dataset.datapoint_list)
        dataset_size = len(dataset.datapoint_list)
        total = sum(categories_ratio.values())
        start = 0
        end = 0

        # TODO ? to assure whole numbers, we round down the division, which leads to lost of several samples. Fix it?
        split_datasets = set()
        for category, ratio in categories_ratio.items():
            size = int(dataset_size * ratio / total)
            end += (size - 1)
            dp_list = dataset.datapoint_list[start:end]

            split_datasets.add(
                Dataset(klass=dataset.klass, branches=dataset.branches, category=category, datapoint_list=dp_list))
            start += size

        return split_datasets

    @classmethod
    def merge_by_category(cls, set_of_datasets):
        datasets_by_category = {}
        for dataset in set_of_datasets:
            if dataset.category not in datasets_by_category.keys(): datasets_by_category.update({dataset.category: []})
            datasets_by_category[dataset.category].append(dataset)

        final_datasets = set()
        for category, datasets in datasets_by_category.items():
            branches = datasets[0].branches
            merged_datapoint_list = []
            for dataset in datasets:
                merged_datapoint_list += dataset.datapoint_list
            final_datasets.add(
                cls(branches=branches, category=category, datapoint_list=merged_datapoint_list))

        return final_datasets

    def __init__(self, klass=None, branches=None, category=None, bed_file=None, win=None, winseed=None,
                 datapoint_list=[]):
        self.branches = branches  # list of seq, cons or fold branches
        self.klass = klass  # e.g. positive or negative
        self.category = category  # train, validation, test or blackbox for separated datasets
        self.datapoint_list = datapoint_list

        if bed_file and win:
            self.datapoint_list = self.read_in_bed(bed_file, win, winseed)

    def read_in_bed(self, bed_file, window, window_seed):
        datapoint_list = []
        file = open(bed_file)

        for line in file:
            values = line.split()

            chrom_name = values[0]
            # first position in chr in bed file is assigned as 0 (thus it fits the python indexing from 0)
            seq_start = int(values[1])
            # both bed file coordinates and python range exclude the last position
            seq_end = int(values[2])
            if len(values) >= 6:
                strand_sign = values[5]
            else:
                strand_sign = None

            if chrom_name in seq.VALID_CHRS:
                datapoint = DataPoint(self.branches, self.klass, chrom_name, seq_start, seq_end, strand_sign,
                                      win=window, winseed=window_seed)
                datapoint_list.append(datapoint)

        return datapoint_list

    def reduce(self, ratio, seed):
        random.seed(seed)
        random.shuffle(self.datapoint_list)
        last = int(len(self.datapoint_list) * ratio)

        self.datapoint_list = self.datapoint_list[0:last]
        return self

    def values(self, branch):
        # return ordered list of values of datapoints
        values = []
        for datapoint in self.datapoint_list:
            values.append(datapoint.value(branch))

        return np.array(values)

    def labels(self, alphabet=None):
        # return ordered list of values of datapoints
        labels = []
        for datapoint in self.datapoint_list:
            labels.append(datapoint.klass)

        if alphabet:
            encoded_labels = [seq.translate(item, alphabet) for item in labels]
            return np.array(encoded_labels)
        else:
            return np.array(labels)

    def map_to_branches(self, references, encoding, strand, outfile_path, ncpu):
        out_file = Dataset.initialize_file(outfile_path, self.branches)

        for branch in self.branches:
            # TODO complementarity currently applied only to sequence. Does the conservation score depend on strand?
            reference = references[branch]
            if branch == 'seq':
                self.datapoint_list = self.map_to_fasta_dict(self.datapoint_list, branch, reference, encoding, strand)
            elif branch == 'cons':
                self.datapoint_list = self.map_to_wig(branch, self.datapoint_list, reference)
            elif branch == 'fold':
                datapoint_list = self.map_to_fasta_dict(self.datapoint_list, branch, reference, False, strand)
                logger.debug('Folding sequences in {} dataset...'.format(self.category))
                file_name = 'fold' + '_' + self.category
                # TODO probably the input may not be DNA, should the user define it? Or should we check it somewhere?
                self.datapoint_list = self.fold_branch(file_name, datapoint_list, ncpu, dna=True)

        for datapoint in self.datapoint_list:
            datapoint.write(out_file)
        out_file.close()

        logger.debug('Compressing final {} dataset...'.format(self.category))
        zipped = ZipFile("{}.zip".format(outfile_path), 'w')
        zipped.write(outfile_path, os.path.basename(outfile_path), compress_type=ZIP_DEFLATED)
        zipped.close()
        os.remove(outfile_path)

        return self

    def sort_datapoints(self):
        self.datapoint_list.sort(key=lambda dp: (seq.VALID_CHRS.index(dp.chrom_name), dp.seq_start))
        return self

    @staticmethod
    def map_to_fasta_dict(datapoint_list, branch, ref_dictionary, encoding, strand):
        # Returns only successfully mapped datapoints
        updated_datapoint_list = []
        for datapoint in datapoint_list:
            if datapoint.chrom_name in ref_dictionary.keys():
                sequence = []
                for i in range(datapoint.seq_start, datapoint.seq_end):
                    sequence.append(ref_dictionary[datapoint.chrom_name][i])

                if strand and datapoint.strand_sign == '-':
                    sequence = seq.complement(sequence, seq.DNA_COMPLEMENTARY)

                if encoding:
                    sequence = [seq.translate(item, encoding) for item in sequence]

                datapoint.branches_values.update({branch: np.array(sequence)})
                updated_datapoint_list.append(datapoint)

        return updated_datapoint_list

    @staticmethod
    def map_to_wig(branch, datapoint_list, ref_folder):
        # TODO document in place
        not_found_chrs = set()
        chrom_files = f.list_files_in_dir(ref_folder, 'wig')

        current_file = None
        current_chr = None
        current_header = {}
        parsed_line = {}

        # Returns only successfully mapped datapoints
        updated_datapoint_list = []
        for datapoint in datapoint_list:
            print("next DP")
            dp_len = datapoint.seq_end - datapoint.seq_start
            dp_start = datapoint.seq_start
            chr = datapoint.chrom_name
            score = []

            if chr == current_chr:
                score, current_header, parsed_line = Dataset.map_datapoint_to_wig(
                    score, dp_start, dp_len, current_file, current_header, parsed_line)
            elif chr in not_found_chrs:
                continue
            else:
                files = list(filter(lambda f: "{}.".format(datapoint.chrom_name) in os.path.basename(f), chrom_files))
                if len(files) == 1:
                    if current_file:
                        current_file.close()
                    current_chr = datapoint.chrom_name
                    print("Moved to chr {}".format(current_chr))
                    current_file = f.unzip_if_zipped(files[0])
                    if ".gz" in current_file or ".zip" in current_file:
                        zipped = True
                    else:
                        zipped = False
                    line = f.read_decoded_line(current_file, zipped)
                    # Expecting first line of the file to be a header
                    current_header = seq.parse_wig_header(line)
                    score, current_header, parsed_line = Dataset.map_datapoint_to_wig(
                        score, dp_start, dp_len, current_file, current_header, parsed_line)
                else:
                    not_found_chrs.add(datapoint.chrom_name)
                    if len(files) == 0:
                        # TODO or rather raise an exception to let user fix it?
                        logger.info("Didn't find appropriate conservation file for {}, skipping the chromosome.".format(chr))
                    else:  # len(files) > 1
                        logger.info("Found multiple conservation files for {}, skipping the chromosome.".format(chr))
                    continue

            # TODO remove testing condition
            print(score)
            if len(score) == dp_len:
                datapoint.branches_values.update({branch: np.array(score)})
            else:
                raise Exception("Parsed score of wrong length, {} instead of {}".format(len(score), dp_len))
            updated_datapoint_list.append(datapoint)

        return updated_datapoint_list

    @staticmethod
    def map_datapoint_to_wig(score, dp_start, dp_len, current_file, current_header, parsed_line):
        print(dp_start, current_header['start'])
        line = current_file.readline()
        new_score = []
        if 'chrom' in line:
            current_header = seq.parse_wig_header(line)
            new_score, current_header, parsed_line = Dataset.map_datapoint_to_wig(
                score, dp_start, dp_len, current_file, current_header, parsed_line)
        else:
            if dp_start < current_header['start']:
                logger.info("Overstepped a datapoint!")
            else:
                current_header, parsed_line = seq.parse_wig_line(line, current_header)
                if dp_start in parsed_line.keys():
                    for i in range(0, dp_len):
                        coord = dp_start + i
                        if coord in parsed_line.keys():
                            score.append(parsed_line[coord])
                        else:
                            new_score, current_header, parsed_line = Dataset.map_datapoint_to_wig(
                                score, dp_start+i, dp_len-i, current_file, current_header, parsed_line)
                            break
                else:
                    new_score, current_header, parsed_line = Dataset.map_datapoint_to_wig(
                        score, dp_start, dp_len, current_file, current_header, parsed_line)

        return [score.append(new_score), current_header, parsed_line]

    @staticmethod
    def fold_branch(file_name, datapoint_list, ncpu, dna=True):
        tmp_dir = tempfile.gettempdir()
        fasta_file = Dataset.datapoints_to_fasta(datapoint_list, 'fold', tmp_dir, file_name)

        out_path = os.path.join(tmp_dir, file_name + "_folded")
        out_file = open(out_path, 'w+')
        if dna:
            # TODO mustard converts DNA to RNA also on its own, ask why not to use the --noconv option instead
            subprocess.run(["RNAfold", "--noPS", "--jobs=".format(ncpu), fasta_file], stdout=out_file, check=True)
        else:
            subprocess.run(["RNAfold", "--noPS", "--noconv", "--jobs=".format(ncpu), fasta_file], stdout=out_file, check=True)

        out_file = open(out_path)
        lines = out_file.readlines()
        out_file.close()

        if (len(lines) / 3) == len(datapoint_list):
            # The order should remain the same as long as --unordered is not set to True
            updated_datapoint_list = []
            fold_encoding = seq.onehot_encode_alphabet(['.', '|', 'x', '<', '>', '(', ')'])
            for i, line in enumerate(lines):
                # We're interested only in each third line in the output file (there are 3 lines per one input sequence)
                if (i + 1) % 3 == 0:
                    datapoint = datapoint_list[int(i / 3)]
                    value = []
                    # line format: '.... (0.00)'
                    part1 = line.split(' ')[0].strip()
                    for char in part1:
                        value.append(seq.translate(char, fold_encoding))
                    datapoint.branches_values.update({'fold': np.array(value)})
                    updated_datapoint_list.append(datapoint)
        else:
            raise Exception('Did not fold all the datapoints!')
            # We have no way to determine which were not folded if this happens
            sys.exit()

        return updated_datapoint_list

    @staticmethod
    def initialize_file(path, branches):
        out_file = open(path, 'w')
        header = 'key' + '\t' + '\t'.join(branches) + '\n'
        out_file.write(header)
        return out_file

    @staticmethod
    def datapoints_to_fasta(datapoint_list, branch, path, name):
        path_to_fasta = os.path.join(path, (name + ".fa"))
        content = ""
        for datapoint in datapoint_list:
            line1 = ">" + datapoint.key() + "\n"
            line2 = ''.join(datapoint.value(branch)) + "\n"
            content += line1
            content += line2

        f.write(path_to_fasta, content.strip())
        return path_to_fasta
