"""

Functions for plotting SIVAK-results. All functions require the class pySIVAK with a loaded model as argument

"""


import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from pathlib import Path
import seaborn as sns
import pandas as pd
import numpy as np


def barplot_passagetime_per_shiptype(S):
    plotdata = S.transit_times.groupby('Class')['Passage time (hours)'].mean() * 60

    plotdata.plot.barh(figsize=(4, 6), zorder=3)
    plt.xlabel('Passeertijd (min)')
    plt.ylabel('')
    plt.grid()
    plt.gca().invert_yaxis()
    return plotdata


def heatmap_passagetime_per_hour_per_day(S):
    # Difference in weekday
    plotdata = S.passage_time_per_hour_per_day()
    plt.figure(figsize=(10, 4))
    sns.heatmap(plotdata.T, cbar=False, cbar_kws={'label': 'Passeer tijd (min)'}, cmap='Reds', annot=True, fmt='.0f',
                annot_kws={'size': 8})
    plt.ylabel('Dag')
    plt.xlabel('Uur')
    plt.title('Gemiddelde passeertijd (min)')
    return plotdata


def heatmap_passagetime_per_hour_per_day_sum(S):
    plotdata = S.passage_time_per_hour_per_day_per_ship_sum().fillna(0).sum(axis=1).unstack().fillna(0)
    plt.figure(figsize=(10, 4))
    sns.heatmap(plotdata.T, cbar=False, cbar_kws={'label': 'Passeer tijd (min)'}, cmap='Oranges', annot=True, fmt='.0f',
                annot_kws={'size': 8})
    plt.ylabel('Dag')
    plt.xlabel('Uur')
    plt.title('Som passeertijd (min)')
    return plotdata


def heatmap_waitingtime_per_hour_per_day_sum(S):
    plotdata = S.passage_time_per_hour_per_day_per_ship_sum(waiting_time=True).fillna(0).sum(axis=1).unstack().fillna(0)
    plt.figure(figsize=(10, 4))
    sns.heatmap(plotdata.T, cbar=False, cbar_kws={'label': 'Passeer tijd (min)'}, cmap='Oranges', annot=True, fmt='.0f',
                annot_kws={'size': 8})
    plt.ylabel('Dag')
    plt.xlabel('Uur')
    plt.title('Som wachttijd (min)')
    return plotdata


def heatmap_waterloss_per_hour_per_day(S):
    # Difference in weekday
    plotdata = S.waterloss_per_hour_per_day()
    plt.figure(figsize=(10, 4))
    sns.heatmap(plotdata.T, cbar=False, cbar_kws={'label': 'Afvoer ($m^3/s$)'}, cmap='Blues', annot=True, fmt='.0f',
                annot_kws={'size': 8}, vmin=0, vmax=30)
    plt.ylabel('Dag')
    plt.xlabel('Uur')
    plt.title('Schutdebiet ($m^3/s$)')
    return plotdata


def barplot_ships_per_leveling(S):
    t = S.ships_per_leveling()

    plotdata = pd.concat({
        'Zonder recreatievaart': t.iloc[:, t.columns < 1].sum(axis=1),
        'Met recreatievaart': t.iloc[:, t.columns >= 1].sum(axis=1),
    }, axis=1)

    plotdata = plotdata.reindex(np.arange(0, 5, 1))
    plotdata.plot.bar(stacked=True, width=0.8, zorder=3)
    plt.grid()
    plt.xlabel('Beroepsvaart per schutting')
    plt.ylabel('Aantal schuttingen per week')
    return plotdata


def barplot_passagetime(S):
    plotdata = (S.transit_times.groupby('Chamber')[['Waiting time (hours)',
                                                    'Demurrage time (hours)',
                                                    'Leveling time (hours)', ]].mean() * 60)

    plotdata.rename(columns={
        'Waiting time (hours)': 'Wachttijd',
        'Demurrage time (hours)': 'Overligtijd',
        'Leveling time (hours)': 'Schuttijd'
    }, inplace=True)

    plotdata.plot.bar(stacked=True, figsize=(3, 4), width=0.8, zorder=3)

    plt.gca().legend(*map(reversed, plt.gca().get_legend_handles_labels()), loc='center left',
                     bbox_to_anchor=(1, 0.5))
    plt.ylabel('Tijd (minuten)')
    plt.grid()
    plt.xlabel('Kolk')
    return plotdata


def heatmap_utilization(S):
    plotdata = S.utilization(n_bins=5)

    f, ax = plt.subplots(figsize=(4, 3))
    sns.heatmap(plotdata.T + 1e-10, annot=True, fmt='.0f', cbar=False, vmax=100, vmin=0,
                norm=LogNorm(vmin=0.1, vmax=100), cmap='Reds')
    plt.xlabel('Bezetting open zijde')
    plt.ylabel('Bezetting gesloten zijde')
    ax.invert_yaxis()
    return plotdata


def histogram_waitingtime(S):
    plotdata = S.transit_times['Total waiting time (hours)']
    plotdata = plotdata * 60

    t_criterium = 30

    plotdata.plot.hist(density=True, cumulative=True, bins=100, zorder=3)
    plt.xlabel('Wachttijd (min)')
    plt.axvline(t_criterium, c='k', ls=':', zorder=4)
    plt.grid()
    plt.ylabel('Frequentie')
    plt.xlim(right=plotdata.max())
    plt.ylim(0, 1)

    n_above_criterium = (plotdata > t_criterium).sum() / S.replications
    n_above_criterium_percentage = n_above_criterium / (plotdata.count() / S.replications)
    plt.annotate(f'{n_above_criterium:.0f} ({n_above_criterium_percentage:.0%})', (0.95, 0.05),
                 xycoords='axes fraction', ha='right', c='white')

    return plotdata


def plot_and_save_all(S, outputdir):
    outputdir = Path(outputdir)
    outputdir.mkdir(exist_ok=True, parents=True)

    plotdata = barplot_passagetime_per_shiptype(S)

    plt.savefig(outputdir / 'Passeertijd_scheepstype.png', bbox_inches='tight', dpi=150)
    plt.savefig(outputdir / 'Passeertijd_scheepstype.svg', bbox_inches='tight')
    plt.close()
    plotdata.to_csv(outputdir / 'Passeertijd_scheepstype.csv')

    plotdata = heatmap_passagetime_per_hour_per_day(S)

    plt.savefig(outputdir / 'Passeertijd_dag_uur.png', bbox_inches='tight', dpi=150)
    plt.savefig(outputdir / 'Passeertijd_dag_uur.svg', bbox_inches='tight')
    plt.close()
    plotdata.to_csv(outputdir / 'Passeertijd_dag_uur.csv')

    plotdata = heatmap_passagetime_per_hour_per_day_sum(S)

    plt.savefig(outputdir / 'Passeertijd_dag_uur_som.png', bbox_inches='tight', dpi=150)
    plt.savefig(outputdir / 'Passeertijd_dag_uur_som.svg', bbox_inches='tight')
    plt.close()
    plotdata.to_csv(outputdir / 'Passeertijd_dag_uur_som.csv')

    plotdata = heatmap_waitingtime_per_hour_per_day_sum(S)

    plt.savefig(outputdir / 'Wachttijd_dag_uur_som.png', bbox_inches='tight', dpi=150)
    plt.savefig(outputdir / 'Wachttijd_dag_uur_som.svg', bbox_inches='tight')
    plt.close()
    plotdata.to_csv(outputdir / 'Wachttijd_dag_uur_som.csv')

    plotdata = heatmap_waterloss_per_hour_per_day(S)

    plt.savefig(outputdir / 'Schutdebiet.png', bbox_inches='tight', dpi=150)
    plt.savefig(outputdir / 'Schutdebiet.svg', bbox_inches='tight')
    plt.close()
    plotdata.to_csv(outputdir / 'Schutdebiet.csv')

    plotdata = barplot_ships_per_leveling(S)

    plt.savefig(outputdir / 'Schuttingen_beroepsvaart.png', bbox_inches='tight', dpi=150)
    plt.savefig(outputdir / 'Schuttingen_beroepsvaart.svg', bbox_inches='tight')
    plt.close()
    plotdata.to_csv(outputdir / 'Schuttingen_beroepsvaart.csv')

    plotdata = barplot_passagetime(S)

    plt.savefig(outputdir / 'Passeertijd.png', bbox_inches='tight', dpi=150)
    plt.savefig(outputdir / 'Passeertijd.svg', bbox_inches='tight')
    plt.close()
    plotdata.to_csv(outputdir / 'Passeertijd.csv')

    plotdata = heatmap_utilization(S)

    plt.savefig(outputdir / 'Bezetting.png', bbox_inches='tight', dpi=150)
    plt.savefig(outputdir / 'Bezetting.svg', bbox_inches='tight')
    plt.close()
    plotdata.to_csv(outputdir / 'Bezetting.csv')

    plotdata = histogram_waitingtime(S)

    plt.savefig(outputdir / 'Wachttijd_verdeling.png', bbox_inches='tight', dpi=150)
    plt.savefig(outputdir / 'Wachttijd_verdeling.svg', bbox_inches='tight')
    plt.close()
    plotdata.to_csv(outputdir / 'Wachttijd_verdeling.csv')
