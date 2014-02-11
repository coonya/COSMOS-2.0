import os
import sys

def get_last_cmd_executed():
    cmd_args = [a if ' ' not in a else "'" + a + "'" for a in sys.argv[1:]]
    return '$ ' + ' '.join([os.path.basename(sys.argv[0])] + cmd_args)

def add_execution_args(parser):
    parser.add_argument('-n', '--name',
                        help="A name for this execution", required=True)
    # parser.add_argument('-q', '--default_queue', type=str,
    #                     help="Default queue.  Defaults to the value in cosmos.session.settings.")
    parser.add_argument('-o', '--output_dir', type=str,
                        help="The directory to output files to.  Path should not exist if this is a new execution.")
    parser.add_argument('-c', '--max_cpus', type=int,
                        help="Maximum number (based on the sum of cpu_requirement) of cores to use at once.  0 means"
                             "unlimited", default=None)
    parser.add_argument('-r', '--restart', action='store_true',
                        help="Completely restart the execution.  Note this will delete all record of the execution in"
                             "the database")
    parser.add_argument('-y', '--prompt_confirm', action='store_false',
                        help="Do not use confirmation prompts before restarting or deleting, and assume answer is"
                             "always yes.")


def parse_and_start(parser, session, root_output_dir=None):
    """
    Parses the args of :param:`parser`

    :param root_output_dir: if output_dir is None, it will be set to root_output_dir/execution_name

    :returns: (Execution, dict kwargs)
    """
    parsed = parser.parse_args()
    kwargs = dict(parsed._get_kwargs())

    from kosmos import Execution

    d = {n: kwargs[n] for n in ['name', 'output_dir', 'restart', 'prompt_confirm', 'max_cpus']}
    if d['output_dir'] is None:
        assert root_output_dir and os.path.exists(root_output_dir),\
            'root_output_dir `%s` does not exist.' % root_output_dir

        d['output_dir'] = os.path.join(root_output_dir, d['name'])
    ex = Execution.start(session=session, **d)
    session.commit()
    return ex, kwargs



def default_argparser(session, root_output_dir='.'):
    """
    Creates an argparser with all of the default options.  On a successful argparse,
    calls and returns the output of :func:`parse_and_start`

    :returns: (Execution, dict kwargs)
    """
    import argparse

    p = argparse.ArgumentParser()
    add_execution_args(p)
    return parse_and_start(p, session, root_output_dir=root_output_dir)