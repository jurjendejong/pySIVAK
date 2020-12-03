"""

Class for reading and postprocessing SIVAK output

"""

from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.colors import LogNorm

class pySIVAK:
    
    
    def __init__(self, ships_file: Path, levelings_file: Path, transit_times_file: Path, summary_file: Path=None):
        
        self.name = ships_file.stem.split('(')[1].split(')')[0]
        
        # Read all data
        self.ships = pd.read_excel(ships_file).set_index(['Replication Id', 'Ship'])
        self.levelings = pd.read_excel(levelings_file).set_index(['Replication Id', 'Lock Leveling ID'])
        self.transit_times = pd.read_excel(transit_times_file).set_index(['Replication Id', 'Ship'])
        
        if summary_file is not None:
            self.summary = pd.read_excel(summary_file, index_col='Chamber')
        else:
            self.summary = self.summary_compute()
        
        self.replications = self.ships.index.levels[0].max()

        # Formatting
        self.transit_times['Time'] = pd.to_datetime(self.transit_times['Time'], format='%d-%m-%Y %H:%M:%S')

        for c in ['Start Doors Closing', 'Start Leveling', 'Start Doors Opening', 'Start Sailing Out', 'End Sailing Out']:
            self.levelings[c] = pd.to_datetime(self.levelings[c], format='%d-%m-%Y %H:%M:%S')
        
        # Joins
        self.transit_times = self.transit_times.join(self.ships, rsuffix='_shiplog')
        
        
        
    def summary_compute():
        # Wrong way to reproduce, mean of all passage times of all replicas
        passage_time = S[scenario].transit_times.groupby('Chamber')['Passage time (hours)'].mean() * 60
        # Good way to reproduce (first per replica, than mean of replicas)
        # passage_time = (S[scenario].transit_times.reset_index().groupby(['Replication Id', 'Chamber'])['Passage time (hours)'].mean() * 60 ).unstack().mean()

        # Cannot reproduce, is SIVAK correct?

        # Average waiting time of all trips
        waiting_time = S[scenario].transit_times.groupby('Chamber')['Waiting time (hours)'].mean() * 60
        # Average waiting time per replica, than averaged
        # waiting_time = (S[scenario].transit_times.reset_index().groupby(['Replication Id', 'Chamber'])['Waiting time (hours)'].mean() * 60).unstack().mean()

        # Average utilization of all levelings
        utilization = S[scenario].levelings.reset_index().groupby(['Lock Chamber'])['Utilization open side (%)'].mean()
        # Average utilization per replica, than averaged
        # utilization = S[scenario].levelings.reset_index().groupby(['Lock Chamber', 'Replication Id'])['Utilization open side (%)'].mean().unstack().mean(axis=1)

        # Number of levelings, per replica, than averaged (method does not matter)
        n_levelings = S[scenario].levelings.reset_index().groupby(['Lock Chamber', 'Replication Id'])['Lock'].count().unstack().mean(axis=1)

        # Number of empty levelings, per replica, than averaged (method does not matter)
        n_levelings_empty = S[scenario].levelings[S[scenario].levelings['Nb of Ships'] == 0].reset_index().groupby(['Lock Chamber', 'Replication Id'])['Lock'].count().unstack().mean(axis=1)

        # Number of ships, per replica, than averaged (method does not matter)
        n_ships = S[scenario].levelings.reset_index().groupby(['Lock Chamber', 'Replication Id'])['Nb of Ships'].sum().unstack().mean(axis=1)

        lock_name = S[scenario].levelings.groupby('Lock Chamber')['Lock'].first()

        self.summary = pd.concat({
            'Lock': lock_name,
            'Amount of ships': n_ships,
            'Amount of levelings': n_levelings,
            'Amount of empty levelings': n_levelings_empty,
            'Avg passage time (minutes)': passage_time,
            'Avg waiting time (minutes)': waiting_time,
            'Avg Utilization (%)': utilization
        }, axis=1)
    
    
    def waterloss_per_hour_per_day(self):
        s = self.levelings.groupby([self.levelings['Start Leveling'].dt.hour, self.levelings['Start Leveling'].dt.day])['Waterloss (m3)'].sum()
        s = s.unstack().fillna(0)  # Formatting
        s = s / self.replications  # Correct for replications
        s = s / 60 / 60 # Per hour to per second
        return s
    
    def passage_time_per_hour_per_day(self, sum=False):
        s = self.transit_times.groupby([self.transit_times['Time'].dt.hour, self.transit_times['Time'].dt.day])['Passage time (hours)'].mean()
        s = s.unstack()  # Formatting
        s = s* 60 # Hours to minutes
        return s
    
    def passage_time_per_hour_per_day_per_ship_sum(self):
        s = self.transit_times.groupby([self.transit_times['Time'].dt.hour, self.transit_times['Time'].dt.day, self.transit_times['Class']])['Passage time (hours)'].sum()
        s = s.unstack()  # Formatting
        s = s / self.replications
        s = s* 60 # Hours to minutes
        return s
        
    def utilization(self, n_bins=5):
        # What part of the chamber is filled?
        
        l = self.levelings.copy()
        
        # Split in bins, add a -0.1 to also have an 'Empty' bin
        bins = [-0.1] + list(np.linspace(0, 100, n_bins))
        labels = ['0%'] + [f'{s}% - {e}%' for s, e in zip(bins[1:-1], bins[2:])]
        
        # Discretise into bins
        l['Utilization open side (%)'] = pd.cut(bins=bins, x=l['Utilization open side (%)'], labels=labels)
        l['Utilization closed side (%)'] = pd.cut(bins=bins, x=l['Utilization closed side (%)'], labels=labels)
        
        # Sum to matrix
        utilization = l.groupby(['Utilization open side (%)', 'Utilization closed side (%)'])['Lock'].count().fillna(0).unstack()
        utilization = utilization / self.replications

        return utilization
    
    def ships_per_leveling(self):
        # Count number of commercial and recreational vessels per lock leveling
        t = self.transit_times.reset_index().groupby(['Replication Id', 'Lock Leveling ID', 'Recreational'])['Ship'].count().unstack('Recreational').fillna(0)
        t = t.rename(columns={True:'Recreational', False:'Commercial'})  # Set type of ship instead of simply True/False

        # Count all combinations of commercial and recreational
        t = t.reset_index().groupby(['Commercial', 'Recreational'])['Lock Leveling ID'].count().unstack().fillna(0)

        # Total ships per leveling
        ships_per_leveling = self.levelings['Nb of Ships'].value_counts().sort_index()
        
        # Add no ships value to the matrix
        t.loc[0, 0] = ships_per_leveling[0]  
        
        t = t / self.replications
        
        return t