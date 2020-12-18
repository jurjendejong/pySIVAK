import numpy as np


class SluisHevelend:
    g = 9.81

    def __init__(self, A_hevelen, A, H, O_A, O_B=None, alpha=None, gamma=1, T_l=None, T_l_hevelen=None):
        """
        This class contains both a mathematical and numerical to simulate hevelend schutten in a lock.

        The mathematical model is sufficient for most computations (e.g. volume, max height) and also for time series
        of leveling for simple models (e.g. only normal levelling, or first fully finish hevelend before starting
        normal). It is however not not sufficient when (1) hevelend and normal leveling is applied at the same time and
        (2) the slowly transitioning to normal leveling before hevelend is already over. For this last point an
        approximation is included where pipes are assumed to be already open if t > T_l and are assumed to be partly
        open (as far as they would have been at this level without hevelend) when t < T_l.

        The numerical model does not have such problems, but is somewhat slower and dependent on a timestep dt.

        :param A_hevelen: Doorstroomoppervlakte x coef van hevelende mechaniek
        :param A: Doorstroomoppervlakte x coef van nivelleer mechaniek
        :param H: head difference (m)
        :param O_A: area of chamber A
        :param O_B: use either alpha or O_B, not both
        :param alpha: use eitehr alpha or O_B, not both
        :param gamma: between 0 and 1 (part of levelings with hevelend)
        :param T_l: time for opening for normal leveling
        :param T_l_hevelen: time for opening the hevelend openings
        """

        self.O_A = O_A
        self.A_hevelen = A_hevelen
        self.A = A
        self.H = H
        self.gamma = gamma
        self.T_l = T_l
        self.T_l_hevelen = T_l_hevelen

        if alpha is None:
            self.O_B = O_B
            self.alpha = O_B / O_A
        else:
            self.alpha = alpha
            self.O_B = self.O_A * alpha

    @property
    def hoogte_hevelend(self):
        H_hevelend_max = self.alpha / (1 + self.alpha) * self.H
        H_hevelend = H_hevelend_max * self.gamma  # Eerder stoppen met hevelend schutten
        return H_hevelend

    #     @property
    #     def hoogte_rest(self):
    #         H_rest = self.H - self.hoogte_hevelend
    #         # or: H_rest = 1/(1+alpha)*H
    #         return H_rest

    @property
    def tijd_hevelend(self):
        H_hevelend = self.hoogte_hevelend
        t = self.tijdserie_hevelend(z_range=[H_hevelend])
        T = t[-1]
        return T

    @property
    def tijd_rest(self):
        H_hevelend = self.hoogte_hevelend
        H = self.H
        t = self.tijdserie_rest(z_range=[H_hevelend, H])
        T = t[-1] - t[0]
        return T

    @property
    def tijd_totaal(self):
        T = self.tijd_hevelend + self.tijd_rest
        return T

    @property
    def volume_schutten(self):
        """
        Het volume dat nog normaal geschut moet worden bij toepassen hevelen
        :return: volume (m3)
        """
        # Som van beide schutkolken
        V_0 = (self.O_A + self.O_B) * self.H

        V_hevelend = V_0 * (1 + 2*self.alpha * (1-self.gamma) + self.alpha ** 2) / (1 + self.alpha) ** 2
        return V_hevelend

    @property
    def volumeaandeel_waterbesparing(self):
        """
        Besparing van inzet hevelend schutten als fractie van het totale schutvolume V_0
        :return: fractie (0-1)
        """
        q = 2 * self.alpha*self.gamma / (1 + self.alpha) ** 2
        return q

    def tijdserie_hevelend(self, z_range):

        A_hevelen = self.A_hevelen
        alpha = self.alpha
        O_A = self.O_A
        H = self.H
        g = self.g
        z_range = np.array(z_range)
        T_l_hevelen = self.T_l_hevelen

        t = lambda z: (-2 * O_A) / (A_hevelen * np.sqrt(2 * g) * (1 / alpha + 1)) * (
                (H - z * (1 / alpha + 1)) ** 0.5 - H ** 0.5)

        if T_l_hevelen is not None:
            t_while_lifting = lambda z: np.sqrt(2*T_l_hevelen * t(z))

            t_while_lifting_range = t_while_lifting(z_range)
            t_range = t(z_range)

            delta_t = T_l_hevelen / 2
            t_range = t_range + delta_t

            ii = t_while_lifting_range < T_l_hevelen
            t_range = np.concatenate([t_while_lifting_range[ii], t_range[~ii]])

        else:
            t_range = t(z_range)


        # For gamma= 1.0, z=hoogte_hevelend this converges to:
        # T = (2 * O_A) / (A_hevelen*np.sqrt(2*g)*(1/alpha+1)) * H**0.5
        return t_range

    def tijdserie_rest(self, z_range):

        A = self.A
        O_A = self.O_A
        H = self.H
        g = self.g
        T_l = self.T_l
        tijd_hevelend = self.tijd_hevelend
        z_range = np.array(z_range)

        t = lambda z: (-2 * O_A) / (A * np.sqrt(2 * g)) * ((H - z) ** 0.5 - H ** 0.5)

        # Only apply correction for slowly opening if time already spent leveling with hevelend is shorter than
        # this time
        if (T_l is not None) and (tijd_hevelend < T_l):
            t_while_lifting = lambda z: np.sqrt(2*T_l * t(z))

            t_while_lifting_range = t_while_lifting(z_range)
            t_range = t(z_range)

            # Deel van de reeks waar nog lifting
            ii = t_while_lifting_range < T_l

            # Correct timeseries to start when hevelend is finished
            t_while_lifting_range = t_while_lifting_range - t_while_lifting_range[0] + tijd_hevelend

            # Correct timeseries to start when opening is finished
            delta_t = t_while_lifting_range[ii][-1] - t_range[ii][-1]
            t_range = t_range + delta_t

            # Combine arrays
            t_range = np.concatenate([t_while_lifting_range[ii], t_range[~ii]])

        else:
            t_range = t(z_range)

            # Start timeseries where tijd_hevelend ends
            t_range = t_range - t_range[0] + tijd_hevelend

        # For z=H this converges to:
        # T = (2 * O_A) / (A_hevelen*np.sqrt(2*g)*(1/alpha+1)) * H**0.5

        return t_range

    def tijdserie(self):

        H_hevelend = self.hoogte_hevelend
        H = self.H

        z_range_hevelend = np.linspace(0, H_hevelend, 100)
        t_range_hevelend = self.tijdserie_hevelend(z_range_hevelend)

        z_range_rest = np.linspace(H_hevelend, H, 100)
        t_range_rest = self.tijdserie_rest(z_range_rest)

        # Combine timeseries
        z_range_totaal = np.concatenate([z_range_hevelend, z_range_rest[1:]])
        t_range_totaal = np.concatenate([t_range_hevelend, t_range_rest[1:]])

        return z_range_totaal, t_range_totaal

    def tijdseries_numeriek(self, tijd_start_normaal=None, tijd_stop_hevelen=None):


        A_hevelen = self.A_hevelen
        A = self.A
        alpha = self.alpha
        O_A = self.O_A
        O_B = self.O_B
        H = self.H
        g = self.g
        T_l_hevelen = self.T_l_hevelen
        T_l = self.T_l


        if tijd_start_normaal is None:
            tijd_start_normaal = self.tijd_hevelend
        tijd_start_normaal = np.max([tijd_start_normaal, 0])

        if tijd_stop_hevelen is None:
            tijd_stop_hevelen = self.tijd_hevelend

        # Functions
        Q_hevelend = lambda z, t_open: A_hevelen * np.sqrt(2*g * (H-z*(1/alpha+1))) * np.min([t_open/T_l_hevelen, 1])
        Q_normaal = lambda z, t_open: A * np.sqrt(2*g * (H-z)) * np.min([t_open/T_l, 1])


        # Initial conditions
        t = 0
        z_A = 0
        z_B = H

        delta_t = 1.

        t_series = []
        z_series = []

        while z_A < H:
            Q = 0

            if z_A < z_B and t < tijd_stop_hevelen:
                Q += Q_hevelend(z_A, t)

            if t > tijd_start_normaal:
                Q += Q_normaal(z_A, t-tijd_start_normaal)

            z_A += Q/O_A
            z_B -= Q/O_B

            t += delta_t
            t_series.append(t)
            z_series.append(z_A)

        return z_series, t_series


if __name__ == '__main__':
    alpha = 1
    A = 7  # Doorstroomoppervlakte x coef van nivelleer mechaniek
    A_hevelen = 2.5  # Doorstroomoppervlakte x coef van hevelende mechaniek
    O_A = 2500
    H = 10.85
    T_l = 300
    T_l_hevelen = 300

    S = SluisHevelend(A_hevelen=A_hevelen, A=A, H=H, O_A=O_A, alpha=1, T_l=T_l, T_l_hevelen=T_l_hevelen)

    # print(S.tijd_totaal)
    # print(S.tijdserie())

    S.gamma = 0.15
    z, t = S.tijdserie()