"""

Create plots for all simulations

"""


from pySIVAK import pySIVAK
import pySIVAK_plots as plots

from pathlib import Path
import logging
import json

logging.basicConfig(level=logging.INFO)


inputdir = Path(r'../../data_results')
settingsdir = Path('Invoer')

with open(settingsdir / 'settings.json') as f:
      settings = json.load(f)
        
water_plane = settings['water_plane']
dH = settings['dH']

with open(settingsdir / 'simulations.json') as f:
      simulations = json.load(f)

for lock in ['Maasbracht', 'Born', 'Heel']:
    SIVAK_scenarios = simulations[lock]

    for scenario, scenario_name in SIVAK_scenarios.items():
        logging.info(f'{scenario} - {scenario_name}')
        summary_file =       inputdir / lock / 'KPI LockChambers Summary' / f'KPI_LockChambers_Summary_Avg ({scenario}).xlsx'
        ships_file =         inputdir / lock / 'Log Generated Ships' / f'Log Generated Ships ({scenario}).xlsx'
        levelings_file =     inputdir / lock / 'Log Locks Leveling' / f'Log Locks Leveling ({scenario}).xlsx'
        transit_times_file = inputdir / lock / 'Log Locks Transit Times' / f'Log Locks Transit Times ({scenario}).xlsx'

        if not ships_file.exists():
            ships_file = None
            continue

        s = pySIVAK(levelings_file, transit_times_file, ships_file, summary_file)
        
        outputdir = Path('Simulation_results') / lock / scenario_name / 'zonder_postprocessing'
        outputdir.mkdir(exist_ok=True, parents=True)

        plots.plot_and_save_all(s, outputdir=outputdir)
        
        maximum_waiting_time = float(scenario_name.split(' ')[-1]) / 60 if scenario_name.startswith("R ") else 9999
        s.correction_waitingtimes_without_new_arrivals(maximum_waiting_time=maximum_waiting_time)
        s.correction_leveling_without_utilization()
        s.correction_waterloss(water_plane=water_plane[lock], dH=dH[lock], downward_leveling_side=1, correct_ship_volume=True)
        
        outputdir = Path('Simulation_results') / lock / scenario_name
        
        plots.plot_and_save_all(s, outputdir=outputdir)