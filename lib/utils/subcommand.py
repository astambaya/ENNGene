import argparse
from datetime import datetime
import os
import sys


class Subcommand:

    def __init__(self, parser):
        self.args = parser.parse_args(sys.argv[2:])

        self.gpu = self.args.gpu

        if self.args.ncpu == 0:
            self.ncpu = os.cpu_count() or 1
        else:
            self.ncpu = self.args.ncpu

        if self.args.output:
            self.output_folder = self.args.output
        else:
            self.output_folder = os.path.join(os.getcwd(), 'output')
        self.ensure_dir(self.output_folder)

        self.verbose = self.args.verbose

    @staticmethod
    def initialize_parser(subcommand_help):
        parser = argparse.ArgumentParser(
            description='rbp deepnet',
            usage=subcommand_help
        )
        parser.add_argument(
            "-o", "--output",
            dest='output',
            help="Specify folder for output files. If not specified, current working directory will be used."
        )
        parser.add_argument(
            "--ncpu",
            default=0,
            type=int,
            help="Number of CPUs to be used. 0 to use all available CPUs. Default: 0."
        )
        parser.add_argument(
            "--gpu",
            help="Use available GPU. Default: False.",
            default=False,
            type=bool
        )

        # TODO do we need verbose and quiet, or rather use the logger for everything?
        # Or use it to set level of logger verbosity?
        parser.add_argument(
            "-v", "--verbose",
            action="store_true",
            dest="verbose",
            default=True,
            help="make lots of noise [default]"
        )
        parser.add_argument(
            "-q", "--quiet",
            action="store_false",
            dest="verbose",
            help="be vewwy quiet (I'm hunting wabbits)"
        )
        return parser

    @staticmethod
    def spent_time(time1):
        time2 = datetime.now()
        t = time2 - time1
        return t

    @staticmethod
    def ensure_dir(dir_path):
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
