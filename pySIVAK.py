"""

Class for reading and postprocessing SIVAK output

Jurjen de Jong, Deltares, 3-12-2020

"""

from pathlib import Path
import pandas as pd
import numpy as np
import itertools
import logging

logging.basicConfig(level=logging.INFO)


class pySIVAK:

    def __init__(self, levelings_file: Path, transit_times_file: Path, ships_file: Path = None,
                 summary_file: Path = None,
                 replications: list = None):
        """

        :param ships_file:
        :param levelings_file:
        :param transit_times_file:
        :param summary_file:
        :param replications: list of replications
        """

        self.name = levelings_file.stem.split('(')[1].split(')')[0]

        # Read all data
        self.levelings = pd.read_excel(levelings_file).set_index(['Replication Id', 'Lock Leveling ID'])
        self.transit_times = pd.read_excel(transit_times_file).set_index(['Replication Id', 'Ship'])

        if ships_file is not None:
            self.ships = pd.read_excel(ships_file).set_index(['Replication Id', 'Ship'])
            self.transit_times = self.transit_times.join(self.ships, rsuffix='_shiplog')
        else:
            logging.info('Ships file not giving, some features might not work')

        # Only select specific replications
        if replications is not None:
            self.ships.reindex(replications, axis=0, level=0)

        if summary_file is not None:
            self.summary = pd.read_excel(summary_file, index_col='Chamber')
        else:
            self.summary_compute()

        # Get number of replications
        self.replications = self.levelings.index.levels[0].max()

        # Formatting
        self.transit_times['Time'] = pd.to_datetime(self.transit_times['Time'], format='%d-%m-%Y %H:%M:%S')

        for c in ['Start Doors Closing', 'Start Leveling', 'Start Doors Opening', 'Start Sailing Out',
                  'End Sailing Out']:
            self.levelings[c] = pd.to_datetime(self.levelings[c], format='%d-%m-%Y %H:%M:%S')

    def correction_leveling_without_utilization(self) -> None:
        """ Remove levelings without utilization """
        l = self.levelings
        ii = (l['Utilization open side (%)'] > 0) | (l['Utilization closed side (%)'] > 0)
        self.levelings = l.loc[ii]

    def correction_waitingtimes_without_new_arrivals(self, maximum_waiting_time) -> None:
        """
        This functions correct the SIVAK output to correct for ships that are now
        waiting for the maximum_waiting_time to pass, while there is not a single
        ship going to arrive within that time slot.

        maximum_waiting_time: hours
        """

        d = self.transit_times

        n_correct = []
        for r, direction in itertools.product(d.index.levels[0], d['Direction'].unique()):
            # Analyse per direction
            d_dir = d.reindex([r], axis=0, level=0).loc[d['Direction'] == direction]
            time_until_next_vessel = d_dir['Time'].diff(periods=1).shift(-1).dt.total_seconds() / 60 / 60

            # Get all vessels that have a current waiting time longer than max and
            # where it also take longer than max for a next vessel to arrive
            ii_correct = (d_dir['Waiting time (hours)'] >= maximum_waiting_time) & (
                    time_until_next_vessel >= maximum_waiting_time)
            n_correct.extend(ii_correct.index[ii_correct])

        # Set waiting time to 0 hours
        d.loc[n_correct, 'Waiting time (hours)'] = 0

        # Also recompute derived statistics
        d['Total waiting time (hours)'] = d['Waiting time (hours)'] + d['Demurrage time (hours)']
        d['Passage time (hours)'] = d['Total waiting time (hours)'] + d['Leveling time (hours)']

        self.transit_times = d

    def correction_waterloss(self, water_plane: dict = None, dH: float = None, downward_leveling_side: int = 1,
                             correct_ship_volume: bool = True) -> None:
        """
        This function recomputes the waterloss, based on the water plane dimensions and the volume of the ships.

        The water loss is defined as the volume lost at the upper level. So for each downward leveling we win
        V_ship_downwards (upon sailing into chamber) and for each upward leveling we lose V_chamber (while leveling)
        and V_ship_upwards (upon sailing out of the chamber).

        This definition of waterloss results in the 'win' of water for downward leveling to have a negative sign.

        :param water_plane: dict of water_plane (m2) per chamber. leave empty to use the current values.
        :param dH: float of head loss (m). Only used when water_plane is specified
        :param downward_leveling_side: which leveling side is downward (and the other is upward).
        :type correct_ship_volume: optional to disable correction for the ship volume
        """

        l = self.levelings
        t = self.transit_times

        if correct_ship_volume:
            # LOA is too long. Better would be LPP
            Cd = 0.9  # Assume shape coefficient
            t['Volume (m3)'] = t['Width (m)'] * t['LOA (m)'] * t['Depth Actual (m)'] * Cd

        for i, r in l.iterrows():

            # Compute waterloss of leveling only if water_plan is giving
            if water_plane is not None:

                # Only for upward levelings
                if r['Side'] == downward_leveling_side:
                    waterloss_row = 0
                else:
                    waterloss_row = dH * water_plane[r['Lock Chamber']]
            else:
                waterloss_row = r['Waterloss (m3)']

            # Compute volume of ships going with the leveling
            if correct_ship_volume:

                ii = t.loc[i[0], 'Lock Leveling ID'] == i[1]
                ships = t.loc[i[0]][ii]
                ship_volume = ships['Volume (m3)']
                total_ship_volume = ship_volume.sum()

                if r['Side'] == downward_leveling_side:
                    total_ship_volume = -1 * total_ship_volume

                l.loc[i, 'Total Ship Volume (m3)'] = total_ship_volume

                waterloss_row = waterloss_row + total_ship_volume

            l.loc[i, 'Waterloss (m3)'] = waterloss_row

    def summary_compute(self) -> None:
        """
        Function to reproduce the summary results pf SIVAK.
        Also some corrections are done, where the SIVAK defaults did not seem logical
        """
        # Wrong way to reproduce, mean of all passage times of all replicas
        passage_time = self.transit_times.groupby('Chamber')['Passage time (hours)'].mean() * 60
        # Good way to reproduce (first per replica, than mean of replicas)
        # passage_time = (S[scenario].transit_times.reset_index().groupby(
        #   ['Replication Id', 'Chamber'])['Passage time (hours)'].mean() * 60 ).unstack().mean()

        # Average waiting time of all trips
        waiting_time = self.transit_times.groupby('Chamber')['Waiting time (hours)'].mean() * 60
        # Average waiting time per replica, than averaged
        # waiting_time = (S[scenario].transit_times.reset_index().groupby(
        #   ['Replication Id', 'Chamber'])['Waiting time (hours)'].mean() * 60).unstack().mean()

        # Average utilization of all levelings
        utilization = self.levelings.reset_index().groupby(['Lock Chamber'])['Utilization open side (%)'].mean()
        # Average utilization per replica, than averaged
        # utilization = S[scenario].levelings.reset_index().groupby(
        #   ['Lock Chamber', 'Replication Id'])['Utilization open side (%)'].mean().unstack().mean(axis=1)

        # Number of levelings, per replica, than averaged (method does not matter)
        n_levelings = self.levelings.reset_index().groupby(['Lock Chamber', 'Replication Id'])[
            'Lock'].count().unstack().mean(axis=1)

        # Number of empty levelings, per replica, than averaged (method does not matter)
        n_levelings_empty = self.levelings[self.levelings['Nb of Ships'] == 0].reset_index().groupby(
            ['Lock Chamber', 'Replication Id'])['Lock'].count().unstack().mean(axis=1)

        # Number of ships, per replica, than averaged (method does not matter)
        n_ships = self.levelings.reset_index().groupby(['Lock Chamber', 'Replication Id'])[
            'Nb of Ships'].sum().unstack().mean(axis=1)

        lock_name = self.levelings.groupby('Lock Chamber')['Lock'].first()

        self.summary = pd.concat({
            'Lock': lock_name,
            'Amount of ships': n_ships,
            'Amount of levelings': n_levelings,
            'Amount of empty levelings': n_levelings_empty,
            'Avg passage time (minutes)': passage_time,
            'Avg waiting time (minutes)': waiting_time,
            'Avg Utilization (%)': utilization
        }, axis=1)

    def waterloss_per_hour_per_day(self) -> pd.DataFrame:
        """
        Total water loss per hour based

        :return:
        """

        l = self.levelings
        s = l.groupby([l['Start Leveling'].dt.hour, l['Start Leveling'].dt.day])['Waterloss (m3)'].sum()
        s = s.unstack().fillna(0)  # Formatting
        s = s / self.replications  # Correct for replications
        s = s / 60 / 60  # Per hour to per second
        return s

    def passage_time_per_hour_per_day(self) -> pd.DataFrame:
        """
        Compute 2D matrix of the average passage time (minutes) per per hour per day
        """
        s = self.transit_times.groupby([self.transit_times['Time'].dt.hour, self.transit_times['Time'].dt.day])[
            'Passage time (hours)'].mean()
        s = s.unstack()  # Formatting
        s = s * 60  # Hours to minutes
        return s

    def passage_time_per_hour_per_day_per_ship_sum(self, waiting_time: bool = False) -> pd.DataFrame:
        """
        Compute 3D matrix of the sum of all passage time (minutes) per per hour per day per ship
        :type waiting_time: Set to True computes waiting_time instead of passage_time
        """

        if not waiting_time:
            column = 'Passage time (hours)'
        else:
            column = 'Waiting time (hours)'

        s = self.transit_times.groupby(
            [self.transit_times['Time'].dt.hour, self.transit_times['Time'].dt.day, self.transit_times['Class']])[
            column].sum()
        s = s.unstack()  # Formatting
        s = s / self.replications
        s = s * 60  # Hours to minutes
        return s

    def utilization(self, n_bins=5) -> pd.DataFrame:
        """
        Compute 2D matrix with on the axis the utilization open/closed binned to n_bins. This function puts all
        levelings in the corresponding bin of the matrix.

        :type n_bins: Number of bins (5 --> [0, 1-25, 25-50, 50-75, 75-100] )

        return: pandas Dataframe
        """

        l = self.levelings.copy()

        # Split in bins, add a -0.1 to also have an 'Empty' bin, the other 0% to 1%
        bins = [-0.1] + list(np.linspace(0, 100, n_bins))
        labels = ['0%'] + [f'{s:.0f}% - {e:.0f}%' for s, e in zip([1.] + bins[2:-1], bins[2:])]

        # Discretise into bins
        l['Utilization open side (%)'] = pd.cut(bins=bins, x=l['Utilization open side (%)'], labels=labels)
        l['Utilization closed side (%)'] = pd.cut(bins=bins, x=l['Utilization closed side (%)'], labels=labels)

        # Sum to matrix
        utilization = l.groupby(['Utilization open side (%)', 'Utilization closed side (%)'])['Lock'].count().fillna(
            0).unstack()
        utilization = utilization / self.replications

        return utilization

    def ships_per_leveling(self) -> pd.DataFrame:
        """
        Count number of commercial and recreational vessels per lock leveling
        """
        t = self.transit_times.reset_index().groupby(['Replication Id', 'Lock Leveling ID', 'Recreational'])[
            'Ship'].count().unstack('Recreational').fillna(0)
        t = t.rename(
            columns={True: 'Recreational', False: 'Commercial'})  # Set type of ship instead of simply True/False

        # Count all combinations of commercial and recreational
        t = t.reset_index().groupby(['Commercial', 'Recreational'])['Lock Leveling ID'].count().unstack().fillna(0)

        # Total ships per leveling
        ships_per_leveling = self.levelings['Nb of Ships'].value_counts().sort_index()

        # Add no ships value to the matrix
        t.loc[0, 0] = ships_per_leveling[0]

        t = t / self.replications

        return t
