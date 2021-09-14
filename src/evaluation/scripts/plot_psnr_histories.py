import os
from warnings import warn
import numpy as np
import yaml
from evaluation.utils import (
        get_multirun_cfgs, get_multirun_experiment_names,
        get_multirun_histories, uses_swa_weights)
from evaluation.evaluation import (
        get_median_psnr_history, get_psnr_steady, get_rise_time_to_baseline)
from evaluation.display_utils import (
    data_title_dict, experiment_color_dict, get_title_from_run_spec)
from copy import copy

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

PATH = '/localdata/jleuschn/experiments/deep_image_prior_extension/'

FIG_PATH = '.'

save_fig = True

with open('../runs.yaml', 'r') as f:
    runs = yaml.load(f, Loader=yaml.FullLoader)

data = 'ellipses_lotus_20'

# Additional `run_spec` dict fields:
# 
#     color : str, optional
#         Line color.

runs_to_compare = [
    {
      'experiment': 'no_pretrain',
      # 'color': '#395262',
    },
    {
      'experiment': 'no_pretrain_fbp',
      # 'color': '#6ac5de',
    },
    {
      'experiment': 'pretrain_only_fbp',
      # 'color': '#ff734a',
    },
    {
      'experiment': 'pretrain',
      # 'color': '#9c62b4',
    },
]

baseline_run_idx = 0

runs_title = ''  # None -> auto from run_specs
runs_filename = 'comparison'  # None -> auto from run_specs

plot_settings_dict = {
    'ellipses_lotus_20': {
        'num_iters': 10000,
        'num_iters_inset': 6750,
        'ylim': (None, 33.25),
        'ylim_inset': (29.25, 31.85),
        'psnr0_x_pos': -150,
        'psnr0_x_shift_per_run_idx': {
            0: -200,
        },
        'psnr_steady_y_pos': 32.5,
        'psnr_steady_y_shift_per_run_idx': {
        },
        'inset_axes_rect': [0.245, 0.15, 0.715, 0.525],
        'inset_axes_rect_border': [0.0625, 0.0575],
    },
    'ellipses_lotus_limited_30': {
        'num_iters': 5000,
        'num_iters_inset': 5000,
        'ylim': None,
        'ylim_inset': None,
        'psnr0_x_shift': -75,
        'psnr_steady_y_pos': 28.,
        'psnr_steady_y_shift_per_run_idx': {
        }
    },
}

eval_settings_dict = {
    'ellipses_lotus_20': {
        'psnr_steady_start': -5000,
        'psnr_steady_stop': None,
        'rise_time_to_baseline_remaining_psnr': 0.5,
    },
    'ellipses_lotus_limited_30': {
        'psnr_steady_start': -5000,
        'psnr_steady_stop': None,
        'rise_time_to_baseline_remaining_psnr': 0.5,
    },
}

data_title = data_title_dict[data]

fig, ax = plt.subplots(figsize=(10, 6))

def get_color(run_spec, cfg):
    color = run_spec.get('color')

    if color is None:
        color = experiment_color_dict.get(run_spec['experiment'])
        if color is None:
            color = 'gray'

    return color

def get_label(run_spec, cfg):
    label_parts = [get_title_from_run_spec(run_spec)]

    if cfg['mdl']['load_pretrain_model']:
        if uses_swa_weights(cfg):
            label_parts.append('SWA weights')

    label = ', '.join(label_parts)
    return label

def get_auto_xlim_with_padding(ax, xmin, xmax):
    hmin = ax.axvline(xmin, linestyle='')
    hmax = ax.axvline(xmax, linestyle='')
    xlim = ax.get_xlim()
    hmin.remove()
    hmax.remove()
    del hmin
    del hmax
    return xlim

# xlim = get_auto_xlim_with_padding(ax, -150,
#                                   plot_settings_dict[data]['num_iters'])
xlim = (-500, plot_settings_dict[data]['num_iters'])
xlim_inset = (-200, plot_settings_dict[data]['num_iters_inset'])


axins = ax.inset_axes(plot_settings_dict[data]['inset_axes_rect'])


cfgs_list = []
experiment_names_list = []
histories_list = []

for run_spec in runs_to_compare:
    experiment = run_spec['experiment']
    available_runs = runs['reconstruction'][data][experiment]
    if run_spec.get('name') is not None:
        run = next((r for r in available_runs if
                    r.get('name') == run_spec['name']),
                   None)
        if run is None:
            raise ValueError('Unknown multirun name "{}" for reconstruction '
                             'with data={}, experiment={}'.format(
                                     run_spec['name'], data, experiment))
    else:
        if len(available_runs) > 1:
            warn('There are multiple multiruns listed for reconstruction with '
                 'data={}, experiment={}, selecting the first one.'.format(
                         data, experiment))
        run = available_runs[0]

    if run.get('run_path') is None:
        raise ValueError('Missing run_path specification for reconstruction '
                         'with data={}, experiment={}. Please insert it in '
                         '`runs.yaml`.'.format(data, experiment))

    run_path_multirun = os.path.join(PATH, run['run_path'])
    sub_runs = run_spec.get('sub_runs')

    cfgs = get_multirun_cfgs(
            run_path_multirun, sub_runs=sub_runs)
    experiment_names = get_multirun_experiment_names(
            run_path_multirun, sub_runs=sub_runs)
    histories = get_multirun_histories(
            run_path_multirun, sub_runs=sub_runs)
    if len(cfgs) == 0:
        warn('No runs found at path "{}", skipping.'.format(run_path_multirun))
        continue
    assert all((cfg['data']['name'] == data for cfg in cfgs))
    swa = cfgs[0]['mdl']['load_pretrain_model'] and uses_swa_weights(cfgs[0])
    assert all(((cfg['mdl']['load_pretrain_model'] and uses_swa_weights(cfg))
                == swa) for cfg in cfgs)
    assert all((en == experiment for en in experiment_names))

    num_runs = len(cfgs)
    print('Found {:d} runs at path "{}".'.format(num_runs, run_path_multirun))

    cfgs_list.append(cfgs)
    experiment_names_list.append(experiment_names)
    histories_list.append(histories)


baseline_histories = histories_list[baseline_run_idx]
baseline_psnr_steady = get_psnr_steady(
        [h['psnr'] for h in baseline_histories],
        start=eval_settings_dict[data]['psnr_steady_start'],
        stop=eval_settings_dict[data]['psnr_steady_stop'])

for ax_ in ax, axins:
    h = ax_.axhline(baseline_psnr_steady, color='gray', linestyle='--',
                    zorder=1.5)
    if ax_ is ax:
        baseline_handle = h

run_handles = []
psnr0_handles = []
rise_time_handles = []

for i, (run_spec, cfgs, experiment_names, histories) in enumerate(zip(
        runs_to_compare, cfgs_list, experiment_names_list, histories_list)):

    psnr_histories = [h['psnr'] for h in histories]

    mean_psnr_history = np.mean(psnr_histories, axis=0)
    std_psnr_history = np.std(psnr_histories, axis=0)

    median_psnr_history = get_median_psnr_history(psnr_histories)
    rise_time_to_baseline = get_rise_time_to_baseline(
            psnr_histories, baseline_psnr_steady,
            remaining_psnr=eval_settings_dict[data][
                    'rise_time_to_baseline_remaining_psnr'])
    

    label = get_label(run_spec, cfgs[0])
    color = get_color(run_spec, cfgs[0])

    # for psnr_history in psnr_histories:
    #     ax.plot(psnr_history, color=color, alpha=0.1)

    for ax_ in [ax, axins]:
        ax_.fill_between(range(len(mean_psnr_history)),
                         mean_psnr_history - std_psnr_history,
                         mean_psnr_history + std_psnr_history,
                         color=color, alpha=0.1,
                         # edgecolor=None,
                         )
        h = ax_.plot(mean_psnr_history, label=label, color=color,
                            linewidth=2)
        if ax_ is ax:
            run_handles += h
        h = ax_.plot(rise_time_to_baseline,
                 plot_settings_dict[data]['psnr_steady_y_pos'],
                 '*', color=color, markersize=8)
        if ax_ is ax:
            rise_time_handles += h
        ax_.plot([rise_time_to_baseline, rise_time_to_baseline],
                 [median_psnr_history[rise_time_to_baseline],
                  plot_settings_dict[data]['psnr_steady_y_pos'] +
                          plot_settings_dict[data][
                              'psnr_steady_y_shift_per_run_idx'].get(i, 0)],
                  color=color, linestyle='--', zorder=1.5)
    
    h = ax.plot(plot_settings_dict[data]['psnr0_x_pos'] + plot_settings_dict[data][
                    'psnr0_x_shift_per_run_idx'].get(i, 0),
            mean_psnr_history[0],
            '^', color=color, markersize=8)
    psnr0_handles += h


ax.grid(True, linestyle='-')
ax.set_xlim(xlim)
ax.set_xlabel('Iteration')
ax.set_ylabel('PSNR [dB]')
ax.set_ylim(plot_settings_dict[data]['ylim'])
ax.spines['right'].set_visible(False)
ax.spines['top'].set_visible(False)
# ax.set_xscale('log')

# axins.grid(True, linestyle=':')
axins.set_xlim(xlim_inset)
axins.set_ylim(plot_settings_dict[data]['ylim_inset'])
axins.spines['right'].set_visible(False)
axins.spines['top'].set_visible(False)

ax.add_patch(Rectangle([plot_settings_dict[data]['inset_axes_rect'][0] -
                        plot_settings_dict[data]['inset_axes_rect_border'][0],
                        plot_settings_dict[data]['inset_axes_rect'][1] -
                        plot_settings_dict[data]['inset_axes_rect_border'][1]],
                        plot_settings_dict[data]['inset_axes_rect'][2] + 
                        plot_settings_dict[data]['inset_axes_rect_border'][0] +
                        0.0025,
                        plot_settings_dict[data]['inset_axes_rect'][3] +
                        plot_settings_dict[data]['inset_axes_rect_border'][1] +
                        0.005,
                        transform=ax.transAxes,
                        color='#EEEEEE',
                        zorder=3,
                        ))
# axins_bbox = axins.get_tightbbox(fig.canvas.get_renderer())  # TODO use this?

run_legend = ax.legend(
        handles=run_handles, bbox_to_anchor=(0.5, -0.1), loc='upper center',
        ncol=4, framealpha=1.)
ax.add_artist(run_legend)
psnr0_handle = copy(psnr0_handles[0])
psnr0_handle.set_markerfacecolor('gray')
psnr0_handle.set_markeredgecolor('gray')
rise_time_handle = copy(rise_time_handles[0])
rise_time_handle.set_markerfacecolor('gray')
rise_time_handle.set_markeredgecolor('gray')
symbol_legend = ax.legend(
        [psnr0_handle, rise_time_handle, baseline_handle],
        ['Initial PSNR',
         'Rise time (to $-${:g} dB)'.format(eval_settings_dict[data][
                 'rise_time_to_baseline_remaining_psnr']),
         'Steady PSNR of {}'.format(
                 get_label(runs_to_compare[baseline_run_idx], cfgs[0]))
         # 'Baseline steady PSNR'.format(
         #         get_label(runs_to_compare[baseline_run_idx], cfgs[0]))
        ],
        bbox_to_anchor=(0.5, -0.005), loc='lower center',
        ncol=3, framealpha=1.
        )

if runs_title is None:
    runs_title = ' vs '.join(
            [get_title_from_run_spec(r) for r in runs_to_compare])
title = ('{} on {}'.format(runs_title, data_title) if runs_title != '' else
         data_title)
ax.set_title(title)

if save_fig:
    if runs_filename is None:
        runs_filename = '_vs_'.join(
                [(r['experiment'] if r.get('name') is None
                  else '{}_{}'.format(r['experiment'], r['name']))
                 for r in runs_to_compare])
    filename = '{}_on_{}.pdf'.format(runs_filename, data)
    fig.savefig(os.path.join(FIG_PATH, filename), bbox_inches='tight')
