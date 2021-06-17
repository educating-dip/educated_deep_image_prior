import os
import h5py
import hydra
import numpy as np
from omegaconf import DictConfig
from dataset import get_standard_dataset, get_test_data
from TVAdam import TVAdamReconstructor
from torch.utils.data import DataLoader
from pre_training import Trainer
from copy import deepcopy

@hydra.main(config_path='../', config_name='baselines/tvadamconfg')
def coordinator(cfg : DictConfig) -> None:

    dataset, ray_trafos = get_standard_dataset(cfg.cfgs.data.name, cfg.cfgs.data)
    dataset_test = get_test_data(cfg.cfgs.data.name, cfg.cfgs.data)
    ray_trafo = {'ray_trafo_module': ray_trafos['ray_trafo_module'],
                 'reco_space': dataset.space[1],
                 'observation_space': dataset.space[0]
                 }
    reconstructor = TVAdamReconstructor(**ray_trafo, cfg=cfg)

    if not os.path.exists(cfg.save_reconstruction_path):
        os.makedirs(cfg.save_reconstruction_path)

    filename = os.path.join(cfg.save_reconstruction_path,'recos.hdf5')
    file = h5py.File(filename, 'w')
    dataset = file.create_dataset('recos', shape=(1, )
        + (128, 128), maxshape=(1, ) + (128, 128), dtype=np.float32, chunks=True)

    dataloader = DataLoader(dataset_test, batch_size=1, num_workers=0,
                            shuffle=True, pin_memory=True)

    for i, (noisy_obs, fbp) in enumerate(dataloader):
        reco = reconstructor.reconstruct(noisy_obs.float(), fbp)
        dataset[i] = reco

if __name__ == '__main__':
    coordinator()