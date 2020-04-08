import os
import streamlit as st
import sys
import logging

sys.path.append(os.getcwd())
# TODO could we somehow move the .log file to relevant folder per each run?
logging.basicConfig(filename='app.log',
                    filemode='a',
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p',
                    level=logging.DEBUG)

logger = logging.getLogger('main')
consoleHandler = logging.StreamHandler()
consoleHandler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s',  datefmt='%m/%d/%Y %I:%M:%S %p')
consoleHandler.setFormatter(formatter)
logger.addHandler(consoleHandler)


class DeepNet:

    def __init__(self):
        st.sidebar.title('Deepnet App')

        available_subcommands = {'Preprocess Data': 'make_datasets',
                                 'Train a Model': 'train'}

        subcommand = available_subcommands[st.sidebar.selectbox(
            'Select a task to be run:',
            list(available_subcommands.keys())
        )]

        st.sidebar.markdown('')
        st.sidebar.markdown('[Documentation](https://gitlab.com/RBP_Bioinformatics/deepnet/-/blob/master/README.md)')
        st.sidebar.markdown('[FAQ](https://gitlab.com/RBP_Bioinformatics/deepnet/-/blob/master/FAQ.md)')
        st.sidebar.markdown('[GitLab](https://gitlab.com/RBP_Bioinformatics/deepnet)')

        logger.debug(f'DeepNet started with the following subcommand: {subcommand}')

        module_path = f'lib.{subcommand}.{subcommand}'
        subcommand_class = ''.join(x.title() for x in subcommand.split('_'))
        module = __import__(module_path, fromlist=[subcommand_class])
        # use dispatch pattern to invoke object of class with same name as the subcommand
        subcommand = getattr(module, subcommand_class)
        subcommand()


if __name__ == '__main__':
    DeepNet()
