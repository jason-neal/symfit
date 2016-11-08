from __future__ import division, print_function
import unittest
import warnings
import sympy
import types

import numpy as np
from symfit.api import *
from symfit.core.fit import *
from symfit.distributions import Gaussian

import matplotlib.pyplot as plt
import seaborn


class TestConstrained(unittest.TestCase):
    """
    Tests for the `ConstrainedNumericalLeastSquares` object. This object does
    everything the normal `NumericalLeastSquares` does and more. Tests should
    therefore cover the full range of scenarios `symfit` currently handles.
    """
    def test_simple_kinetics(self):
        """
        Simple kinetics data to test fitting
        """
        tdata = np.array([10, 26, 44, 70, 120])
        adata = 10e-4 * np.array([44, 34, 27, 20, 14])
        a, b, t = variables('a, b, t')
        k, a0 = parameters('k, a0')
        k.value = 0.01
        # a0.value, a0.min, a0.max = 54 * 10e-4, 40e-4, 60e-4
        a0 = 54 * 10e-4

        model_dict = {
            D(a, t): - k * a**2,
            D(b, t): k * a**2,
        }

        ode_model = ODEModel(model_dict, initial={t: 0.0, a: a0, b: 0.0})

        # Generate some data
        tvec = np.linspace(0, 500, 1000)

        fit = ConstrainedNumericalLeastSquares(ode_model, t=tdata, a=adata, b=None)
        fit_result = fit.execute()
        # print(fit_result)
        self.assertAlmostEqual(fit_result.value(k), 4.302875e-01)
        self.assertAlmostEqual(fit_result.stdev(k), 6.447068e-03)

        # A, B = ode_model(t=tvec, **fit_result.params)
        # plt.plot()
        # plt.plot(tvec, A, label='[A]')
        # plt.plot(tvec, B, label='[B]')
        # plt.scatter(tdata, adata)
        # plt.legend()
        # plt.show()

    def test_global_fitting(self):
        """
        Test a global fitting scenario with datasets of unequal length. In this
        scenario, a quartic equation is fitted where the constant term is shared
        between the datasets. (e.g. identical background noise)
        """
        x_1, x_2, y_1, y_2 = variables('x_1, x_2, y_1, y_2')
        y0, a_1, a_2, b_1, b_2 = parameters('y0, a_1, a_2, b_1, b_2')

        # The following vector valued function links all the equations together
        # as stated in the intro.
        model = Model({
            y_1: a_1 * x_1**2 + b_1 * x_1 + y0,
            y_2: a_2 * x_2**2 + b_2 * x_2 + y0,
        })

        # Generate data from this model
        # xdata = np.linspace(0, 10)
        xdata1 = np.linspace(0, 10)
        xdata2 = xdata1[::2] # Make the sets of unequal size

        ydata1, ydata2 = model(x_1=xdata1, x_2=xdata2, a_1=101.3, b_1=0.5, a_2=56.3, b_2=1.1111, y0=10.8)
        # Add some noise to make it appear like real data
        np.random.seed(1)
        ydata1 += np.random.normal(0, 2, size=ydata1.shape)
        ydata2 += np.random.normal(0, 2, size=ydata2.shape)

        xdata = [xdata1, xdata2]
        ydata = [ydata1, ydata2]

        # Guesses
        a_1.value = 100
        a_2.value = 50
        b_1.value = 1
        b_2.value = 1
        y0.value = 10

        sigma_y = np.concatenate((np.ones(20), [2., 4., 5, 7, 3]))

        fit = ConstrainedNumericalLeastSquares(model, x_1=xdata[0], x_2=xdata[1], y_1=ydata[0], y_2=ydata[1], sigma_y_2=sigma_y)
        fit_result = fit.execute()
        # fit_curves = model(x_1=xdata[0], x_2=xdata[1], **fit_result.params)
        self.assertAlmostEqual(fit_result.value(y0), 1.061892e+01, 3)
        self.assertAlmostEqual(fit_result.value(a_1), 1.013269e+02, 3)
        self.assertAlmostEqual(fit_result.value(a_2), 5.625694e+01, 3)
        self.assertAlmostEqual(fit_result.value(b_1), 3.362240e-01, 3)
        self.assertAlmostEqual(fit_result.value(b_2), 1.565253e+00, 3)

    def test_named_fitting(self):
        xdata = np.linspace(1,10,10)
        ydata = 3*xdata**2

        a = Parameter(1.0)
        b = Parameter(2.5)
        x, y = variables('x, y')
        model = {y: a*x**b}

        fit = ConstrainedNumericalLeastSquares(model, x=xdata, y=ydata)
        fit_result = fit.execute()
        self.assertIsInstance(fit_result, FitResults)
        self.assertAlmostEqual(fit_result.value(a), 3.0, 3)
        self.assertAlmostEqual(fit_result.value(b), 2.0, 4)

    def test_param_error_analytical(self):
        """
        Take an example in which the parameter errors are known and see if
        `ConstrainedNumericalLeastSquares` reproduces them.

        It also needs to support the absolute_sigma argument.
        """
        N = 10000
        sigma = 25.0
        xn = np.arange(N, dtype=np.float)
        np.random.seed(110)
        yn = np.random.normal(size=xn.shape, scale=sigma)

        a = Parameter()
        y = Variable()
        model = {y: a}

        constr_fit = ConstrainedNumericalLeastSquares(model, y=yn, sigma_y=sigma)
        constr_result = constr_fit.execute()
        print(constr_result)

        fit = NumericalLeastSquares(model, y=yn, sigma_y=sigma)
        fit_result = fit.execute()
        # print(fit_result)

        self.assertAlmostEqual(fit_result.value(a), constr_result.value(a), 5)
        self.assertAlmostEqual(fit_result.stdev(a), constr_result.stdev(a), 5)

        # Analytical answer for mean of N(0,sigma):
        mu = 0.0
        # mu = np.mean(yn)
        sigma_mu = sigma/N**0.5

        # self.assertAlmostEqual(fit_result.value(a), mu, 5)
        self.assertAlmostEqual(fit_result.value(a), np.mean(yn), 5)
        self.assertAlmostEqual(fit_result.stdev(a), sigma_mu, 5)

        # Compare for absolute_sigma = False.
        constr_fit = ConstrainedNumericalLeastSquares(model, y=yn, sigma_y=sigma, absolute_sigma=False)
        constr_result = constr_fit.execute()
        print(constr_result)

        fit = NumericalLeastSquares(model, y=yn, sigma_y=sigma, absolute_sigma=False)
        fit_result = fit.execute()
        print(fit_result)

        self.assertAlmostEqual(fit_result.value(a), constr_result.value(a), 5)
        self.assertAlmostEqual(fit_result.stdev(a), constr_result.stdev(a), 5)

    def test_grid_fitting(self):
        """
        This fit seems to fail occasionally. WTF? I'm not in the randomness generation business.
        """
        xdata = np.arange(-5, 5, 1)
        ydata = np.arange(5, 15, 1)
        xx, yy = np.meshgrid(xdata, ydata, sparse=False)

        zdata = (2.5*xx**2 + 3.0*yy**2)

        a = Parameter(2.4, max=2.75)
        b = Parameter(3.1, min=2.75)
        x = Variable()
        y = Variable()
        z = Variable()
        new = {z: a*x**2 + b*y**2}

        fit = ConstrainedNumericalLeastSquares(new, x=xx, y=yy, z=zdata)
        # results = fit.execute(options={'maxiter': 10})
        results = fit.execute()

        print(results)

        self.assertAlmostEqual(results.value(a), 2.5, 4)
        self.assertAlmostEqual(results.value(b), 3.0, 4)

    def test_vector_constrained_fitting(self):
        """
        Tests `ConstrainedNumericalLeastSquares` with vector models. The
        classical example of fitting measurements of the angles of a triangle is
        taken. In this case we know they should add up to 180 degrees, so this
        can be added as a constraint. Additionally, not even all three angles
        have to be provided with measurement data since the constrained means
        the angles are not independent.
        """
        a, b, c = parameters('a, b, c')
        a_i, b_i, c_i = variables('a_i, b_i, c_i')

        model = {a_i: a, b_i: b, c_i: c}

        xdata = np.array([
            [10.1, 9., 10.5, 11.2, 9.5, 9.6, 10.],
            [102.1, 101., 100.4, 100.8, 99.2, 100., 100.8],
            [71.6, 73.2, 69.5, 70.2, 70.8, 70.6, 70.1],
        ])

        fit_none = ConstrainedNumericalLeastSquares(
            model=model,
            a_i=xdata[0],
            b_i=xdata[1],
            c_i=None,
        )
        fit = ConstrainedNumericalLeastSquares(
            model=model,
            a_i=xdata[0],
            b_i=xdata[1],
            c_i=xdata[2],
        )
        fit_std = NumericalLeastSquares(
            model=model,
            a_i=xdata[0],
            b_i=xdata[1],
            c_i=xdata[2],
        )
        fit_constrained = ConstrainedNumericalLeastSquares(
            model=model,
            a_i=xdata[0],
            b_i=xdata[1],
            c_i=xdata[2],
            constraints=[Equality(a + b + c, 180)]
        )
        fit_none_result = fit_none.execute()
        fit_new_result = fit.execute()
        std_result = fit_std.execute()
        constr_result = fit_constrained.execute()

        # The total of averages should equal the total of the params by definition
        mean_total = np.mean(np.sum(xdata, axis=0))
        params_tot = std_result.value(a) + std_result.value(b) + std_result.value(c)
        self.assertAlmostEqual(mean_total, params_tot, 4)

        # The total after constraining to 180 should be exactly 180.
        params_tot = constr_result.value(a) + constr_result.value(b) + constr_result.value(c)
        self.assertAlmostEqual(180.0, params_tot, 4)

        # The standard method and the Constrained object called without constraints
        # should behave roughly the same.
        self.assertAlmostEqual(fit_new_result.value(a), std_result.value(a), 4)
        self.assertAlmostEqual(fit_new_result.value(b), std_result.value(b), 4)
        self.assertAlmostEqual(fit_new_result.value(c), std_result.value(c), 4)

        # When fitting with a dataset set to None, for this example the value of c
        # should be unaffected.
        self.assertAlmostEqual(fit_none_result.value(a), std_result.value(a), 4)
        self.assertAlmostEqual(fit_none_result.value(b), std_result.value(b), 4)
        self.assertAlmostEqual(fit_none_result.value(c), c.value)

        fit_none_constr = ConstrainedNumericalLeastSquares(
            model=model,
            a_i=xdata[0],
            b_i=xdata[1],
            c_i=None,
            constraints=[Equality(a + b + c, 180)]
        )
        none_constr_result = fit_none_constr.execute()
        params_tot = none_constr_result.value(a) + none_constr_result.value(b) + none_constr_result.value(c)
        self.assertAlmostEqual(180.0, params_tot, 4)

    def test_vector_parameter_error(self):
        """
        Tests `ConstrainedNumericalLeastSquares` parameter error estimation with
        vector models. This is done by using the typical angles of a triangle
        example. For completeness, we throw in covariance between the angles.

        As it stands now, `ConstrainedNumericalLeastSquares` is able to correctly
        predict the values of the parameters an their standard deviations, but
        it is not able to give the covariances. Those are therefore returned as
        nan, to prevent people from citing them as 0.0.
        """
        N = 10000
        a, b, c = parameters('a, b, c')
        a_i, b_i, c_i = variables('a_i, b_i, c_i')

        model = {a_i: a, b_i: b, c_i: c}

        np.random.seed(1)
        # Sample from a multivariate normal with correlation.
        pcov = np.array([[0.4, 0.3, 0.5], [0.3, 0.8, 0.4], [0.5, 0.4, 1.2]])
        xdata = np.random.multivariate_normal([10, 100, 70], pcov, N).T

        fit = ConstrainedNumericalLeastSquares(
            model=model,
            a_i=xdata[0],
            b_i=xdata[1],
            c_i=xdata[2],
        )
        fit_std = NumericalLeastSquares(
            model=model,
            a_i=xdata[0],
            b_i=xdata[1],
            c_i=xdata[2],
        )
        fit_new_result = fit.execute(tol=1e-9)
        std_result = fit_std.execute()

        # The standard method and the Constrained object called without constraints
        # should give roughly the same parameter values.
        self.assertAlmostEqual(fit_new_result.value(a), std_result.value(a), 3)
        self.assertAlmostEqual(fit_new_result.value(b), std_result.value(b), 3)
        self.assertAlmostEqual(fit_new_result.value(c), std_result.value(c), 3)

        # in this toy model, fitting is identical to simply taking the average
        self.assertAlmostEqual(fit_new_result.value(a), np.mean(xdata[0]), 4)
        self.assertAlmostEqual(fit_new_result.value(b), np.mean(xdata[1]), 4)
        self.assertAlmostEqual(fit_new_result.value(c), np.mean(xdata[2]), 4)

        # The standard object actually does not predict the right values for
        # stdev, because its method for computing them apperantly does not allow
        # for vector valued functions.
        # So actually, for vector valued functions its better to use
        # ConstrainedNumericalLeastSquares.

        # The standerd deviation in the mean is stdev/sqrt(N),
        # see test_param_error_analytical
        self.assertAlmostEqual(fit_new_result.stdev(a), np.std(xdata[0],ddof=1)/np.sqrt(N), 4)
        self.assertAlmostEqual(fit_new_result.stdev(b), np.std(xdata[1],ddof=1)/np.sqrt(N), 4)
        self.assertAlmostEqual(fit_new_result.stdev(c), np.std(xdata[2],ddof=1)/np.sqrt(N), 4)


        # With the correct values of sigma, abslute_sigma=True should be in
        # agreement. with analytical.
        sigmadata = np.array([
            np.std(xdata[0],ddof=1),
            np.std(xdata[1],ddof=1),
            np.std(xdata[2],ddof=1)
        ])
        fit = ConstrainedNumericalLeastSquares(
            model=model,
            a_i=xdata[0],
            b_i=xdata[1],
            c_i=xdata[2],
            sigma_a_i=sigmadata[0],
            sigma_b_i=sigmadata[1],
            sigma_c_i=sigmadata[2],
            # absolute_sigma=False
        )
        fit_result = fit.execute(tol=1e-9)
        self.assertAlmostEqual(fit_result.stdev(a), np.std(xdata[0],ddof=1)/np.sqrt(N), 2)
        self.assertAlmostEqual(fit_result.stdev(b), np.std(xdata[1],ddof=1)/np.sqrt(N), 2)
        self.assertAlmostEqual(fit_result.stdev(c), np.std(xdata[2],ddof=1)/np.sqrt(N), 2)


        # Finally, we should confirm that with unrealistic sigma and
        # absolute_sigma=True, we are no longer in agreement with the analytical result
        # Let's take everything to be 1 to point out the dangers of doing so.
        sigmadata = np.array([1, 1, 1])
        fit2 = ConstrainedNumericalLeastSquares(
            model=model,
            a_i=xdata[0],
            b_i=xdata[1],
            c_i=xdata[2],
            sigma_a_i=sigmadata[0],
            sigma_b_i=sigmadata[1],
            sigma_c_i=sigmadata[2],
        )
        fit_result = fit2.execute(tol=1e-9)
        self.assertNotAlmostEqual(fit_result.stdev(a), np.std(xdata[0],ddof=1)/np.sqrt(N), 3)
        self.assertNotAlmostEqual(fit_result.stdev(b), np.std(xdata[1],ddof=1)/np.sqrt(N), 3)
        self.assertNotAlmostEqual(fit_result.stdev(c), np.std(xdata[2],ddof=1)/np.sqrt(N), 3)

    def test_error_advanced(self):
        """
        Compare the error propagation of ConstrainedNumericalLeastSquares against
        NumericalLeastSquares.
        Models an example from the mathematica docs and try's to replicate it:
        http://reference.wolfram.com/language/howto/FitModelsWithMeasurementErrors.html
        """
        data = [
            [0.9, 6.1, 9.5], [3.9, 6., 9.7], [0.3, 2.8, 6.6],
            [1., 2.2, 5.9], [1.8, 2.4, 7.2], [9., 1.7, 7.],
            [7.9, 8., 10.4], [4.9, 3.9, 9.], [2.3, 2.6, 7.4],
            [4.7, 8.4, 10.]
        ]
        xdata, ydata, zdata = [np.array(data) for data in zip(*data)]
        xy = np.vstack((xdata, ydata))
        # z = np.array(z)
        errors = np.array([.4, .4, .2, .4, .1, .3, .1, .2, .2, .2])

        # raise Exception(xy, z)
        a = Parameter(3.0)
        b = Parameter(0.9)
        c = Parameter(5)
        x = Variable()
        y = Variable()
        z = Variable()
        model = {z: a * log(b * x + c * y)}

        const_fit = ConstrainedNumericalLeastSquares(model, xdata, ydata, zdata)
        const_result = const_fit.execute(tol=1e-8)
        fit = NumericalLeastSquares(model, xdata, ydata, zdata)
        std_result = fit.execute()
        print(const_result)
        print(std_result)

        self.assertAlmostEqual(const_result.value(a), std_result.value(a), 4)
        self.assertAlmostEqual(const_result.value(b), std_result.value(b), 4)
        self.assertAlmostEqual(const_result.value(c), std_result.value(c), 4)

        self.assertAlmostEqual(const_result.stdev(a), std_result.stdev(a), 4)
        self.assertAlmostEqual(const_result.stdev(b), std_result.stdev(b), 4)
        self.assertAlmostEqual(const_result.stdev(c), std_result.stdev(c), 4)

if __name__ == '__main__':
    unittest.main()
