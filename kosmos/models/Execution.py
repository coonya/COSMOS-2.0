from ..db import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, func, event, orm, PickleType, VARCHAR
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import validates, synonym
from flask import url_for
import os, re
import shutil

opj = os.path.join
import signal

from .. import taskgraph, ExecutionFailed
from ..job.JobManager import JobManager
from .. import TaskStatus, Task, __version__, ExecutionStatus, signal_execution_status_change

from ..util.helpers import get_logger, mkdir, confirm
from ..util.sqla import Enum34_ColumnType, MutableDict, JSONEncodedDict
from ..util.args import get_last_cmd_executed


def _default_task_log_output_dir(task):
    """The default function for computing Task.log_output_dir"""
    return opj(task.execution.output_dir, 'log', task.stage.name, str(task.id))


def _default_task_output_dir(task):
    """The default function for computing Task.output_dir"""
    return opj(task.execution.output_dir, task.stage.name, str(task.id))


@signal_execution_status_change.connect
def _execution_status_changed(ex):
    ex.log.info('%s %s, output_dir: %s' % (ex, ex.status, ex.output_dir))

    if ex.status in [ExecutionStatus.successful, ExecutionStatus.failed, ExecutionStatus.killed]:
        ex.finished_on = func.now()

    if ex.status == ExecutionStatus.successful:
        ex.successful = True

    ex.session.commit()


class Execution(Base):
    """
    The primary object.  An Execution is an instantiation of a recipe being run.
    """
    __tablename__ = 'execution'

    id = Column(Integer, primary_key=True)
    name = Column(VARCHAR(200), unique=True)
    description = Column(String(255))
    successful = Column(Boolean, nullable=False, default=False)
    output_dir = Column(String(255), nullable=False)
    created_on = Column(DateTime, default=func.now())
    started_on = Column(DateTime)
    finished_on = Column(DateTime)
    max_cpus = Column(Integer)
    info = Column(MutableDict.as_mutable(JSONEncodedDict))
    #recipe_graph = Column(PickleType)
    _status = Column(Enum34_ColumnType(ExecutionStatus), default=ExecutionStatus.no_attempt)

    exclude_from_dict = ['info']

    @declared_attr
    def status(cls):
        def get_status(self):
            return self._status

        def set_status(self, value):
            if self._status != value:
                self._status = value
                signal_execution_status_change.send(self)

        return synonym('_status', descriptor=property(get_status, set_status))


    @validates('name')
    def validate_name(self, key, name):
        assert re.match('^[\w]+$', name), 'Invalid execution name.'
        return name

    @classmethod
    def start(cls, session, name, output_dir, restart=False, prompt_confirm=True, max_cpus=None):
        """
        Start, resume, or restart an execution based on its name and the session.  If resuming, deletes failed tasks.

        :param session: (sqlalchemy.session)
        :param name: (str) a name for the workflow.
        :param output_dir: (str) the directory to write files to
        :param restart: (bool) if True and the execution exists, delete it first
        :param prompt_confirm: (bool) if True, do not prompt the shell for input before deleting executions or files
        :max_cpus: (int) the maximum number of CPUs to use at once.  Based on the sum of the running tasks' task.cpu_req

        :returns: an instance of Execution
        """
        #assert name is not None, 'name cannot be None'
        assert output_dir is not None, 'output_dir cannot be None'
        old_id = None

        if restart:
            ex = session.query(Execution).filter_by(name=name).first()
            if ex:
                old_id = ex.id
                msg = 'Are you sure you want to `rm -rf %s` and delete all sql records of %s?' % (ex.output_dir, ex)
                if prompt_confirm and not confirm(msg):
                    raise SystemExit('Quitting')

                ex.delete(delete_output_dir=True)

        #resuming?
        ex = session.query(Execution).filter_by(name=name).first()
        msg = 'Execution started, Kosmos v%s' % __version__
        if ex:
            #resuming.
            ex.max_cpus = max_cpus
            if output_dir is None:
                output_dir = ex.output_dir
            else:
                assert ex.output_dir == output_dir, 'cannot change the output_dir of an execution being resumed.'

            ex.log.info(msg)
            session.add(ex)
            q = ex.tasksq.filter_by(successful=False)
            n = q.count()
            if n:
                ex.log.info('Deleting %s failed tasks' % n)
                for t in q.all():
                    session.delete(t)
        else:
            #start from scratch
            assert not os.path.exists(output_dir), '%s already exists' % (output_dir)
            mkdir(output_dir)
            ex = Execution(id=old_id, name=name, output_dir=output_dir, max_cpus=max_cpus)
            ex.log.info(msg)
            session.add(ex)

        ex.info['last_cmd_executed'] = get_last_cmd_executed()
        session.commit()
        return ex

    @orm.reconstructor
    def constructor(self):
        self.__init__()

    def __init__(self, *args, **kwargs):
        super(Execution, self).__init__(*args, **kwargs)
        assert self.output_dir is not None, 'output_dir cannot be None'
        mkdir(self.output_dir)
        self.log = get_logger('kosmos-%s' % Execution, opj(self.output_dir, 'execution.log'))
        if self.info is None:
            self.info = dict()
        self.jobmanager = None

    def run(self, recipe, task_output_dir=_default_task_output_dir, task_log_output_dir=_default_task_log_output_dir,
            settings={},
            parameters={},
            dry=False):
        """
        Executes the :param:`recipe` using the configured :term:`DRM`.

        :param recipe: (Recipe) the Recipe to render and execute.
        :param task_output_dir: a function that computes a tasks' output_dir.
            It receives one parameter: the task instance.  By default task output is stored in
            output_dir/stage_name/task_id.
        :param task_log_output_dir: a function that computes a tasks' log_output_dir.  By default task log output is
            stored in output_dir/log/stage_name/task_id.
        :param settings: (dict) A dict which contains settings used when rendering a recipe to generate the commands.
            keys are stage names and the values are dictionaries that are passed to Tool.cmd() which represents that
            stage as the `s` parameter.
        :param parameters: (dict) Structure is the same as settings, but values are passed to the Tool.cmd() as
            **kwargs.  ex: if parameters={'MyTool':{'x':1}}, then MyTool.cmd will be passed the parameter x=1.
        :param dry: (bool) if True, do not actually run any jobs.

        """
        try:
            session = self.session
            assert session, 'Execution must be part of a sqlalchemy session'
            self.status = ExecutionStatus.running
            self.successful = False

            self.jobmanager = JobManager()
            if self.started_on is None:
                self.started_on = func.now()

            # Render task graph and save to db
            task_g, stage_g = taskgraph.render_recipe(self, recipe, settings=settings, parameters=parameters)
            session.add_all(stage_g.nodes())
            session.add_all(task_g.nodes())
            # Create Task Queue
            task_queue = _copy_graph(task_g)
            successful = filter(lambda t: t.status == TaskStatus.successful, task_g.nodes())
            self.log.info('Skipping %s successful tasks' % len(successful))
            task_queue.remove_nodes_from(successful)
            self.log.info('Queueing %s new tasks' % len(task_queue.nodes()))

            terminate_on_ctrl_c(self)

            session.commit()  # required to set IDs for some of the output_dir generation functions

            # Set output_dirs of new tasks
            log_dirs = {t.log_dir: t for t in successful}
            for task in task_queue.nodes():
                task.output_dir = task_output_dir(task)
                log_dir = task_log_output_dir(task)
                assert log_dir not in log_dirs, 'Duplicate log_dir detected for %s and %s' % (task, log_dirs[log_dir])
                log_dirs[log_dir] = task
                task.log_dir = log_dir
                for tf in task.output_files:
                    if tf.path is None:
                        tf.path = opj(task.output_dir, tf.basename)

            # set commands of new tasks
            for task in task_queue.nodes():
                if not task.NOOP:
                    task.command = task.tool.generate_command(task)

            session.commit()

            if not dry:
                while len(task_queue) > 0:
                    _run_ready_tasks(task_queue, self)
                    for task in _process_finished_tasks(self.jobmanager):
                        task_queue.remove_node(task)

                self.status = ExecutionStatus.successful
            session.commit()

            return self
        except ExecutionFailed as e:
            self.terminate()
            raise

            # except Exception as e:
            #     self.log.error(e)
            #     session.commit()
            #     raise e


    def terminate(self):
        self.log.warning('Terminating!')
        if self.jobmanager:
            self.log.info('Processing finished tasks and terminating running ones')
            _process_finished_tasks(self.jobmanager, at_least_one=False)
            self.jobmanager.terminate()
        self.status = ExecutionStatus.killed


    @property
    def tasksq(self):
        return self.session.query(Task).filter(Task.stage_id.in_(s.id for s in self.stages))


    @property
    def tasks(self):
        return [t for s in self.stages for t in s.tasks]


    def get_stage(self, name_or_id):
        if isinstance(name_or_id, int):
            f = lambda s: s.id == name_or_id
        else:
            f = lambda s: s.name == name_or_id

        for stage in self.stages:
            if f(stage):
                return stage

        raise ValueError('Stage with name %s does not exist' % name_or_id)


    @property
    def url(self):
        return url_for('kosmos.execution', id=self.id)


    def __repr__(self):
        return '<Execution[%s] %s>' % (self.id or '', self.name)


    def delete(self, delete_output_dir=False):
        if delete_output_dir:
            self.log.info('Deleting %s' % self.output_dir)
            shutil.rmtree(self.output_dir)
        self.session.delete(self)
        self.session.commit()

    def yield_outputs(self, name):
        for task in self.tasks:
            tf = task.get_output(name, error_if_missing=False)
            if tf is not None:
                yield tf

    def get_output(self, name):
        r = next(self.yield_outputs(name), None)
        if r is None:
            raise ValueError('Output named `{0}` does not exist in {1}'.format(name, self))
        return r


@event.listens_for(Execution, 'before_delete')
def before_delete(mapper, connection, target):
    print 'before_delete %s ' % target


def _copy_graph(graph):
    import networkx as nx

    graph2 = nx.DiGraph()
    graph2.add_edges_from(graph.edges())
    graph2.add_nodes_from(graph.nodes())
    return graph2


def _run_ready_tasks(task_queue, execution):
    max_cpus = execution.max_cpus
    ready_tasks = [task for task, degree in task_queue.in_degree().items() if
                   degree == 0 and task.status == TaskStatus.no_attempt]
    for ready_task in sorted(ready_tasks, key=lambda t: t.cpu_req):
        cores_used = sum([t.cpu_req for t in execution.jobmanager.running_tasks])
        if max_cpus is not None and ready_task.cpu_req + cores_used > max_cpus:
            execution.log.info('Reached max_cpus limit of %s, waiting for a task to finish...' % max_cpus)
            break

        ## render taskfile paths
        for f in ready_task.output_files:
            if f.path is None:
                f.path = os.path.join(ready_task.output_dir, f.basename)

        execution.jobmanager.submit(ready_task)


def _process_finished_tasks(jobmanager, at_least_one=True):
    for task in jobmanager.get_finished_tasks(at_least_one=at_least_one):
        if task.profile.get('exit_status', None) == 0 or task.NOOP:
            task.status = TaskStatus.successful
            yield task
        else:
            if not task.must_succeed:
                yield task
            task.status = TaskStatus.failed


def terminate_on_ctrl_c(execution):
#terminate on ctrl+c
    try:
        def ctrl_c(signal, frame):
            if not execution.successful:
                execution.log.info('Caught SIGINT (ctrl+c)')
                execution.terminate()
                raise SystemExit('Execution terminated with a SIGINT (ctrl+c) event')

        signal.signal(signal.SIGINT, ctrl_c)
    except ValueError: #signal only works in parse_args thread and django complains
        pass