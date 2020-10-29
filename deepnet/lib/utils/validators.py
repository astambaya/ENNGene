import h5py
import os

from .dataset import Dataset
from . import file_utils as f

BRANCHES_REV = {'seq': 'Sequence',
                'cons': 'Conservation score',
                'fold': 'Secondary structure'}


def not_empty_branches(branches):
    warning = 'You must select at least one branch.'
    return warning if len(branches) == 0 else None


def min_two_files(input_files):
    warning = 'You must provide at least two input files for a classification problem.'
    return warning if len(input_files) < 2 else None


def is_bed(file):
    invalid = False

    if len(file) == 0:
        invalid = True
        warning = 'You must provide the BED file.'
    else:
        if os.path.isfile(file):
            with open(file) as f:
                try:
                    line = f.readline()
                except Exception:
                    invalid = True
                cells = line.split('\t')
                if len(cells) >= 3:
                    try:
                        int(cells[1])
                        int(cells[2])
                    except Exception:
                        invalid = True
                else:
                    invalid = True
            warning = f"File {file} does not look like valid BED file (tab separated)."
        else:
            invalid = True
            warning = f'Given BED file {file} does not exist.'

    return warning if invalid else None


def is_fasta(file):
    invalid = False

    if len(file) == 0:
        invalid = True
        warning = 'You must provide the FASTA file.'
    else:
        if os.path.isfile(file):
            with open(file) as f:
                try:
                    line1 = f.readline()
                    line2 = f.readline()
                except Exception:
                    invalid = True
                if not ('>' in line1) or not line2:
                    invalid = True
            warning = f"File {file} does not look like valid FASTA file."
        else:
            invalid = True
            warning = f'Given FASTA file {file} does not exist.'

    return warning if invalid else None


def is_wig_dir(folder):
    # Checks just one random (first found) wig file
    invalid = False

    if len(folder) == 0:
        invalid = True
        warning = 'You must provide the conservation reference directory.'
    else:
        if os.path.isdir(folder):
            files = f.list_files_in_dir(folder, 'wig')
            one_wig = next((file for file in files if 'wig' in file), None)
            if one_wig:
                zipped = True if ('gz' in one_wig or 'zip' in one_wig) else False
                try:
                    wig_file = f.unzip_if_zipped(one_wig)
                    line1 = f.read_decoded_line(wig_file, zipped)
                    if not ('fixedStep' in line1 or 'variableStep' in line1) or not ('chrom' in line1):
                        invalid = True
                        warning = f"Provided wig file {one_wig} starts with unknown header."
                    line2 = f.read_decoded_line(wig_file, zipped)
                    float(line2)
                except Exception:
                    invalid = True
                    warning = f"Tried to look at a provided wig file: {one_wig} and failed to properly read it. Please check the format."
            else:
                invalid = True
                warning = "I don't see any WIG file in conservation reference directory."
        else:
            invalid = True
            warning = 'Provided conservation reference directory does not exist.'

    return warning if invalid else None


def is_ratio(string):
    invalid = False
    if len(string) == 0:
        invalid = True
        warning = 'You must provide the split ratio.'
    else:
        if (':' in string) and len(string.split(':')) == 4:
            try:
                numbers = [float(part) for part in string.split(':')]
            except Exception:
                invalid = True
                warning = 'All parts of the split ratio must be numbers.'
        else:
            invalid = True
            warning = 'Invalid format of the split ratio.'

    return warning if invalid else None


def is_dataset_dir(folder):
    invalid = False

    if len(folder) == 0:
        invalid = True
        warning = 'You must provide a folder with the preprocessed files.'
    else:
        if os.path.isdir(folder):
            param_files = [file for file in os.listdir(folder) if (file == 'parameters.yaml') and
                           (os.path.isfile(os.path.join(folder, file)))]
            if len(param_files) == 1:
                files = f.list_files_in_dir(folder, 'zip')
                dataset_files = {'train': [], 'validation': [], 'test': [], 'blackbox': []}
                for file in files:
                    category = next((category for category in dataset_files.keys() if category in os.path.basename(file)), None)
                    if category: dataset_files[category].append(file)
                for category, files in dataset_files.items():
                    if category == 'blackbox': continue  # the blackbox dataset is optional
                    if len(files) != 1:
                        invalid = True
                        warning = 'Each category (train, test, validation) must be represented by exactly one preprocessed file in the given folder.'
                    else:
                        if files[0] != f'{category}.zip':
                            invalid = True
                            warning = ''
            else:
                invalid = True
                warning = 'Sorry, there is no parameters.yaml file in the given folder. Make sure to provide the whole ' \
                          'datasets folder (not just the one with final datasets).'
        else:
            invalid = True
            warning = 'Given folder with preprocessed files does not exist.'

    return warning if invalid else None


def is_full_dataset(file_path, branches):
    invalid = False

    if len(file_path) == 0:
        invalid = True
        warning = 'You must provide the mapped file.'
    else:
        try:
            dataset = Dataset.load_from_file(file_path)
            category = dataset.category
            base_columns = ['chrom_name', 'seq_start', 'seq_end', 'strand_sign', 'klass']
            if category or not all(col in dataset.df.columns for col in base_columns):
                invalid = True
                warning = 'Given mapped file does not contain necessary data. Please check the file.'
            if not all(col in dataset.df.columns for col in branches):
                invalid = True
                warning = 'Given mapped file does not contain selected branches.'
        except Exception:
            invalid = True
            warning = 'Sorry, could not parse given mapped file. Please check the file.'

    return warning if invalid else None


def not_empty_chromosomes(chromosomes_list):
    invalid = False
    for category, chromosomes in chromosomes_list:
        if not chromosomes:
            invalid = True
            warning = 'You must select at least one chromosome per each category.'

    return warning if invalid else None


def is_model_file(file_path):
    invalid = False
    if len(file_path) == 0:
        invalid = True
        warning = 'You must provide the hdf5 file with a trained model.'
    else:
        if os.path.isfile(file_path):
            if not h5py.is_hdf5(file_path):
                invalid = True
                warning = 'Given file does not seem to be a valid model (requires hdf5 format).'
        else:
            invalid = True
            warning = 'Given file with model does not exist.'

    return warning if invalid else None


def is_multiline_text(text, alphabet):
    invalid = False
    sequences = text.strip().split('\n')
    if len(text) == 0 or len(sequences) == 0:
        invalid = True
        warning = 'You must provide at least one sequence to be classified.'

    invalid_characters = []
    for sequence in sequences:
        for letter in sequence:
            if letter not in alphabet:
                invalid_characters.append(letter)
    if len(invalid_characters) > 0:
        invalid = True
        warning = f'Given sequences contain invalid characters: {invalid_characters}.'

    return warning if invalid else None