COSMOS is currently BETA.  Although the code is considered stable,
we are planning a major publication before the official release.



For more information and the full documentation please visit
`http://cosmos-wfm.readthedocs.org <http://cosmos-wfm.readthedocs.org>`_.

Install
==========

.. code-block:: python

    pip install cosmos-wfm


Introduction
============

Cosmos is a workflow management system for Python.  It allows you to efficiently program complex workflows of command line tools that automatically take
advantage of a compute cluster, and provides a web dashboard to monitor, debug, and analyze your jobs.  Cosmos is
able to scale on a traditional cluster such as LSF or GridEngine with a shared filesystem.  It is especially
powerful when combined with spot instances on `Amazon Web Services <aws.amazon.com>`_ and
`StarCluster <http://star.mit.edu/cluster/>`_.


History
___________

COSMOS was published as an Application Note in the journal `Bioinformatics <http://bioinformatics.oxfordjournals.org/>`_,
but has evolved a lot since it's original inception.  If you use COSMOS
for research, please cite it's `manuscript <http://bioinformatics.oxfordjournals.org/content/early/2014/06/29/bioinformatics.btu385>`_.  This means a lot to the author.

Since the original publication, it has been re-written and open-sourced by the original author, in a collaboration between
`The Lab for Personalized Medicine <http://lpm.hms.harvard.edu/>`_ at Harvard Medical School, the `Wall Lab <http://wall-lab.stanford.edu/>`_ at Stanford University, and
`Invitae <http://invitae.com>`_, a clinical genetic sequencing diagnostics laboratory.

Features
_________
* Written in python which is easy to learn, powerful, and popular.  A programmer with limited experience can begin writing Cosmos workflows right away.
* Powerful syntax for the creation of complex and highly parallelized workflows.
* Reusable recipes and definitions of tools and sub workflows allows for DRY code.
* Keeps track of workflows, job information, and resource utilization and provenance in an SQL database.
* The ability to visualize all jobs and job dependencies as a convenient image.
* Monitor and debug running workflows, and a history of all workflows via a web dashboard.
* Alter and resume failed workflows.

Multi-platform Support
+++++++++++++++++++++++

* Support for DRMS such as SGE, LSF.  DRMAA coming soon.  Adding support for more DRMs is very straightforward.
* Supports for MySQL, PosgreSQL, Oracle, SQLite by using the SQLALchemy ORM.
* Extremely well suited for cloud computing, especially when used in conjuection with `AWS <http://aws.amazon.com>`_ and `StarCluster <http://star.mit.edu/cluster/>`_.

Bug Reports
____________

Please use the `Github Issue Tracker <https://github.com/LPM-HMS/Cosmos2/issues>`_.

.. image:: https://badges.gitter.im/Join%20Chat.svg
   :alt: Join the chat at https://gitter.im/LPM-HMS/Cosmos2
   :target: https://gitter.im/LPM-HMS/Cosmos2?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge