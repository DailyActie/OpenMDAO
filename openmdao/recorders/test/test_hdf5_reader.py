""" Unit tests for the SqliteCaseReader. """
from __future__ import print_function

import errno
import os
import unittest
from shutil import rmtree
from tempfile import mkdtemp

from openmdao.api import Problem, ScipyOptimizer, Group, \
    IndepVarComp, CaseReader
from openmdao.examples.paraboloid_example import Paraboloid

try:
    from openmdao.recorders.hdf5_recorder import HDF5Recorder, format_version
    from openmdao.recorders.hdf5_reader import HDF5CaseReader
    import h5py
    NO_HDF5 = False
except ImportError:
    # Necessary for the file to parse
    from openmdao.recorders.base_recorder import BaseRecorder
    HDF5Recorder = BaseRecorder
    NO_HDF5 = True
    format_version = None


try:
    from openmdao.drivers.pyoptsparse_driver import pyOptSparseDriver
except ImportError:
    pyOptSparseDriver = None


optimizers = {'scipy': ScipyOptimizer,
              'pyoptsparse': pyOptSparseDriver}


def _setup_test_case(cls, record_params=True, record_resids=True,
                     record_unknowns=True, record_derivs=True,
                     record_metadata=True, optimizer='scipy'):
    cls.dir = mkdtemp()
    cls.filename = os.path.join(cls.dir, "hdf5_test")
    cls.recorder = HDF5Recorder(cls.filename)

    prob = Problem()

    root = prob.root = Group()

    root.add('p1', IndepVarComp('x', 3.0))
    root.add('p2', IndepVarComp('y', -4.0))
    root.add('p', Paraboloid())

    root.connect('p1.x', 'p.x')
    root.connect('p2.y', 'p.y')

    prob.driver = optimizers[optimizer]()

    prob.driver.add_desvar('p1.x', lower=-1, upper=10,
                           scaler=1.0, adder=0.0)
    prob.driver.add_desvar('p2.y', lower=-1, upper=10,
                           scaler=1.0, adder=0.0)
    prob.driver.add_objective('p.f_xy', scaler=1.0, adder=0.0)

    prob.driver.add_recorder(cls.recorder)
    cls.recorder.options['record_params'] = record_params
    cls.recorder.options['record_resids'] = record_resids
    cls.recorder.options['record_unknowns'] = record_unknowns
    cls.recorder.options['record_metadata'] = record_metadata
    cls.recorder.options['record_derivs'] = record_derivs
    prob.setup(check=False)

    prob['p1.x'] = 10.0
    prob['p2.y'] = 10.0

    prob.run()
    prob.cleanup()  # closes recorders


@unittest.skipIf(NO_HDF5, 'HDF5Reader tests skipped.  HDF5 not available.')
class TestHDF5CaseReader(unittest.TestCase):

    def setUp(self):
        _setup_test_case(self, record_params=True, record_metadata=True,
                         record_derivs=True, record_resids=True,
                         record_unknowns=True, optimizer='scipy')

    def tearDown(self):
        try:
            rmtree(self.dir)
        except OSError as e:
            # If directory already deleted, keep going
            if e.errno not in (errno.ENOENT, errno.EACCES, errno.EPERM):
                raise e

    def test_format_version(self):
        cr = CaseReader(self.filename)
        self.assertEqual(cr.format_version, format_version,
                         msg='format version not read correctly')

    def test_reader_instantiates(self):
        """ Test that CaseReader returns an HDF5CaseReader. """
        cr = CaseReader(self.filename)
        self.assertTrue(isinstance(cr, HDF5CaseReader), msg='CaseReader not'
                        ' returning the correct subclass.')

    def test_params(self):
        """ Tests that the reader returns params correctly. """
        cr = CaseReader(self.filename)
        last_case = cr.get_case(-1)
        last_case_id = cr.list_cases()[-1]
        n = cr.num_cases
        with h5py.File(self.filename, 'r') as f:
            for key in f[last_case_id]['Parameters'].keys():
                val = f[last_case_id]['Parameters'][key][()]
                self.assertAlmostEqual(last_case.parameters[key], val,
                                       msg='Case reader gives incorrect '
                                       'Parameter value for {0}'.format(key))

    def test_unknowns(self):
        """ Tests that the reader returns unknowns correctly. """
        cr = CaseReader(self.filename)
        last_case = cr.get_case(-1)
        last_case_id = cr.list_cases()[-1]
        n = cr.num_cases
        with h5py.File(self.filename, 'r') as f:
            for key in f[last_case_id]['Unknowns'].keys():
                val = f[last_case_id]['Unknowns'][key][()]
                self.assertAlmostEqual(last_case[key], val,
                                       msg='Case reader gives incorrect '
                                       'Unknown value for {0}'.format(key))

    def test_resids(self):
        """ Tests that the reader returns resids correctly. """
        cr = CaseReader(self.filename)
        last_case = cr.get_case(-1)
        last_case_id = cr.list_cases()[-1]
        n = cr.num_cases
        with h5py.File(self.filename, 'r') as f:
            for key in f[last_case_id]['Residuals'].keys():
                val = f[last_case_id]['Residuals'][key][()]
                self.assertAlmostEqual(last_case.resids[key], val,
                                       msg='Case reader gives incorrect '
                                       'Unknown value for {0}'.format(key))

    @unittest.skip('Skipped until ScipyOptimizer returns a keyed Jacobian')
    def test_derivs(self):
        """ Test that the reader returns the derivs correctly. """
        cr = CaseReader(self.filename)
        derivs = cr.get_case(-1).derivs
        n = cr.num_cases
        with h5py.File(self.filename, 'r') as f:
            derivs_table = f['rank0:SLSQP|{0}'.format(n)]['Derivatives']
            df_dx = derivs_table['p.f_xy']['p1.x'][()]
            df_dy = derivs_table['p.f_xy']['p2.y'][()]
            self.assertAlmostEqual(derivs['p.f_xy']['p1.x'], df_dx)
            self.assertAlmostEqual(derivs['p.f_xy']['p2.y'], df_dy)


@unittest.skipIf(NO_HDF5, 'HDF5Reader tests skipped.  HDF5 not available.')
class TestHDF5CaseReaderNoParams(TestHDF5CaseReader):

    def setUp(self):
        _setup_test_case(self, record_params=False, record_metadata=True,
                         record_derivs=True, record_resids=True,
                         record_unknowns=True, optimizer='scipy')

    def test_params(self):
        """ Test that params is None if not provided in the recording. """
        cr = CaseReader(self.filename)
        last_case = cr.get_case(-1)
        self.assertIsNone(last_case.parameters,
                          "Case erroneously contains parameters.")


@unittest.skipIf(NO_HDF5, 'HDF5Reader tests skipped.  HDF5 not available.')
class TestHDF5CaseReaderNoResids(TestHDF5CaseReader):

    def setUp(self):
        _setup_test_case(self, record_params=True, record_metadata=True,
                         record_derivs=True, record_resids=False,
                         record_unknowns=True, optimizer='scipy')

    def test_resids(self):
        """ Test that params is None if not provided in the recording. """
        cr = CaseReader(self.filename)
        last_case = cr.get_case(-1)
        self.assertIsNone(last_case.resids,
                          "Case erroneously contains resids.")


@unittest.skip('Skipped until format_version is always recorded')
@unittest.skipIf(NO_HDF5, 'HDF5Reader tests skipped.  HDF5 not available.')
class TestHDF5CaseReaderNoMetadata(TestHDF5CaseReader):
    def setUp(self):
        _setup_test_case(self, record_params=True, record_metadata=False,
                         record_derivs=True, record_resids=True,
                         record_unknowns=True, optimizer='scipy')

    def test_metadata(self):
        """ Test that metadata is correctly read.

        format_version should always be present.
         """
        cr = CaseReader(self.filename)
        self.assertEqual(cr.format_version, format_version,
                         msg='incorrect format version')
        self.assertIsNone(cr.parameters,
                          msg='parameter metadata should be None')
        self.assertIsNone(cr.unknowns, msg='unknown metadata should be None')


@unittest.skipIf(NO_HDF5, 'HDF5Reader tests skipped.  HDF5 not available.')
class TestHDF5CaseReaderNoUnknowns(TestHDF5CaseReader):

    def setUp(self):
        _setup_test_case(self, record_params=True, record_metadata=True,
                         record_derivs=True, record_resids=True,
                         record_unknowns=False, optimizer='scipy')

    def test_unknowns(self):
        """ Test that unknowns is None if not provided in the recording. """
        cr = CaseReader(self.filename)
        last_case = cr.get_case(-1)
        self.assertIsNone(last_case.unknowns,
                          "Case erroneously contains unknowns.")


@unittest.skipIf(NO_HDF5, 'HDF5Reader tests skipped.  HDF5 not available.')
class TestHDF5CaseReaderNoDerivs(TestHDF5CaseReader):

    def setUp(self):
        _setup_test_case(self, record_params=True, record_metadata=True,
                         record_derivs=False, record_resids=True,
                         record_unknowns=True, optimizer='scipy')

    def test_derivs(self):
        """ Test that derivs is None if not provided in the recording. """
        cr = CaseReader(self.filename)
        last_case = cr.get_case(-1)
        self.assertIsNone(last_case.derivs,
                          "Case erroneously contains derivs.")


@unittest.skipIf(True, 'test for skipping capability')
@unittest.skipIf(pyOptSparseDriver is None, 'pyOptSparse not available.')
@unittest.skipIf(NO_HDF5, 'HDF5Reader tests skipped.  HDF5 not available.')
class TestHDF5CaseReaderPyOptSparse(TestHDF5CaseReader):

    def setUp(self):
        _setup_test_case(self, record_params=True, record_metadata=True,
                         record_derivs=True, record_resids=True,
                         record_unknowns=True, optimizer='pyoptsparse')


if __name__ == "__main__":
    unittest.main()
