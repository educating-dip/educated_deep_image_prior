import odl
from odl.contrib.torch import OperatorModule
import torch
import numpy as np
from .ellipses import EllipsesDataset
from . import lotus
from util.matrix_ray_trafo import MatrixRayTrafo
from util.matrix_ray_trafo_torch import get_matrix_ray_trafo_module
from util.fbp import FBP


def subsample_angles_ray_trafo_matrix(matrix, cfg, proj_shape, order='C'):
    prod_im_shape = matrix.shape[1]

    matrix = matrix.reshape(
            (cfg.num_angles_orig, proj_shape[1] * prod_im_shape),
            order=order).tocsc()

    matrix = matrix[cfg.start:cfg.stop:cfg.step, :]

    matrix = matrix.reshape((np.prod(proj_shape), prod_im_shape),
                            order=order).tocsc()
    return matrix


def load_ray_trafo_matrix(name, cfg):

    if name in ['ellipses_lotus', 'ellipses_lotus_20']:
        matrix = lotus.get_ray_trafo_matrix(cfg.ray_trafo_filename)
    else:
        raise NotImplementedError

    return matrix


def get_ray_trafos(name, cfg, return_torch_module=True):
    """
    Return callables evaluating the ray transform and the smooth filtered
    back-projection for a standard dataset.

    The ray trafo can be implemented either by a matrix, which is loaded by
    calling :func:`load_ray_trafo_matrix`, or an odl `RayTransform` is used, in
    which case a standard cone-beam geometry is created.

    Subsampling of angles is supported for the matrix implementation only.

    Optionally, a ray transform torch module can be returned, too.

    Returns
    -------
    ray_trafos : dict
        Dictionary with the entries `'ray_trafo'`, `'smooth_pinv_ray_trafo'`,
        and optionally `'ray_trafo_module'`.
    """

    ray_trafos = {}

    if cfg.geometry_specs.impl == 'matrix':
        matrix = load_ray_trafo_matrix(name, cfg.geometry_specs)
        proj_shape = (cfg.geometry_specs.num_angles,
                      cfg.geometry_specs.num_det_pixels)
        if 'angles_subsampling' in cfg.geometry_specs:
            matrix = subsample_angles_ray_trafo_matrix(
                    matrix, cfg.geometry_specs.angles_subsampling, proj_shape)

        matrix_ray_trafo = MatrixRayTrafo(matrix,
                im_shape=(cfg.im_shape, cfg.im_shape),
                proj_shape=proj_shape)

        ray_trafo = matrix_ray_trafo.apply
        ray_trafos['ray_trafo'] = ray_trafo

        smooth_pinv_ray_trafo = FBP(
                matrix_ray_trafo.apply_adjoint, proj_shape,
                scaling_factor=cfg.fbp_scaling_factor,
                filter_type=cfg.fbp_filter_type,
                frequency_scaling=cfg.fbp_frequency_scaling).apply
        ray_trafos['smooth_pinv_ray_trafo'] = smooth_pinv_ray_trafo

        if return_torch_module:
            ray_trafos['ray_trafo_module'] = get_matrix_ray_trafo_module(
                    matrix, (cfg.im_shape, cfg.im_shape), proj_shape,
                    sparse=True)
    else:
        space = odl.uniform_discr([-cfg.im_shape / 2, -cfg.im_shape / 2],
                                  [cfg.im_shape / 2, cfg.im_shape / 2],
                                  [cfg.im_shape, cfg.im_shape],
                                  dtype='float32')
        geometry = odl.tomo.cone_beam_geometry(space,
                src_radius=cfg.geometry_specs.src_radius,
                det_radius=cfg.geometry_specs.det_radius,
                num_angles=cfg.geometry_specs.num_angles,
                det_shape=cfg.geometry_specs.get('num_det_pixels', None))
        if 'angles_subsampling' in cfg.geometry_specs:
            raise NotImplementedError

        ray_trafo = odl.tomo.RayTransform(space, geometry,
                impl=cfg.geometry_specs.impl)
        ray_trafos['ray_trafo'] = ray_trafo

        smooth_pinv_ray_trafo = odl.tomo.fbp_op(ray_trafo,
                filter_type=cfg.fbp_filter_type,
                frequency_scaling=cfg.fbp_frequency_scaling)
        ray_trafos['smooth_pinv_ray_trafo'] = smooth_pinv_ray_trafo

        if return_torch_module:
            ray_trafos['ray_trafo_module'] = OperatorModule(ray_trafo)

    return ray_trafos


def get_standard_dataset(name, cfg, return_ray_trafo_torch_module=True):
    """
    Return a standard dataset by name.
    """

    name = name.lower()

    ray_trafos = get_ray_trafos(name, cfg,
            return_torch_module=return_ray_trafo_torch_module)

    ray_trafo = ray_trafos['ray_trafo']
    smooth_pinv_ray_trafo = ray_trafos['smooth_pinv_ray_trafo']

    if cfg.noise_specs.noise_type == 'white':
        specs_kwargs = {'stddev': cfg.noise_specs.stddev}
    elif cfg.noise_specs.noise_type == 'poisson':
        specs_kwargs = {'mu_water': cfg.noise_specs.mu_water,
                        'photons_per_pixel': cfg.noise_specs.photons_per_pixel
                        }
    else:
        raise NotImplementedError

    if name == 'ellipses':
        dataset_specs = {'image_size': cfg.im_shape, 'train_len': cfg.train_len,
                         'validation_len': cfg.validation_len, 'test_len': cfg.test_len}
        ellipses_dataset = EllipsesDataset(**dataset_specs)
        dataset = ellipses_dataset.create_pair_dataset(ray_trafo=ray_trafo,
                pinv_ray_trafo=smooth_pinv_ray_trafo, noise_type=cfg.noise_specs.noise_type,
                specs_kwargs=specs_kwargs,
                noise_seeds={'train': cfg.seed, 'validation': cfg.seed + 1,
                'test': cfg.seed + 2})
    elif name == 'ellipses_lotus':
        dataset_specs = {'image_size': cfg.im_shape, 'train_len': cfg.train_len,
                         'validation_len': cfg.validation_len, 'test_len': cfg.test_len}
        ellipses_dataset = EllipsesDataset(**dataset_specs)
        space = lotus.get_domain128()
        proj_space = lotus.get_proj_space128()
        dataset = ellipses_dataset.create_pair_dataset(ray_trafo=ray_trafo,
                pinv_ray_trafo=smooth_pinv_ray_trafo,
                domain=space, proj_space=proj_space,
                noise_type=cfg.noise_specs.noise_type,
                specs_kwargs=specs_kwargs,
                noise_seeds={'train': cfg.seed, 'validation': cfg.seed + 1,
                'test': cfg.seed + 2})
    elif name == 'ellipses_lotus_20':
        dataset_specs = {'image_size': cfg.im_shape, 'train_len': cfg.train_len,
                         'validation_len': cfg.validation_len, 'test_len': cfg.test_len}
        ellipses_dataset = EllipsesDataset(**dataset_specs)
        space = lotus.get_domain128()
        proj_space_orig = lotus.get_proj_space128()
        angles_coord_vector = proj_space_orig.grid.coord_vectors[0][
                cfg.geometry_specs.angles_subsampling.start:
                cfg.geometry_specs.angles_subsampling.stop:
                cfg.geometry_specs.angles_subsampling.step]
        proj_space = odl.uniform_discr_frompartition(
                odl.uniform_partition_fromgrid(
                        odl.RectGrid(angles_coord_vector,
                                     proj_space_orig.grid.coord_vectors[1])))
        dataset = ellipses_dataset.create_pair_dataset(ray_trafo=ray_trafo,
                pinv_ray_trafo=smooth_pinv_ray_trafo,
                domain=space, proj_space=proj_space,
                noise_type=cfg.noise_specs.noise_type,
                specs_kwargs=specs_kwargs,
                noise_seeds={'train': cfg.seed, 'validation': cfg.seed + 1,
                'test': cfg.seed + 2})
    else:
        raise NotImplementedError

    return dataset, ray_trafos


def get_test_data(name, cfg, return_torch_dataset=True):
    """
    Return external test data.

    E.g., for `'ellipses_lotus'` the scan of the lotus root is returned for
    evaluating a model trained on the `'ellipses_lotus'` standard dataset.

    Sinograms, FBPs and potentially ground truth images are returned, by
    default combined as a torch `TensorDataset` of two or three tensors.

    If `return_torch_dataset=False` is passed, numpy arrays
    ``sinogram_array, fbp_array, ground_truth_array`` are returned, where
    `ground_truth_array` can be `None` and all arrays have shape ``(N, W, H)``.
    """

    if cfg.test_data == 'lotus':
        sinogram, fbp, ground_truth = get_lotus_data(name, cfg)
        sinogram_array = sinogram[None]
        fbp_array = fbp[None]
        ground_truth_array = (ground_truth[None] if ground_truth is not None
                              else None)
    else:
        raise NotImplementedError

    if return_torch_dataset:
        if ground_truth_array is not None:
            dataset = torch.utils.data.TensorDataset(
                        torch.from_numpy(sinogram_array[:, None]),
                        torch.from_numpy(fbp_array[:, None]),
                        torch.from_numpy(ground_truth_array[:, None]))
        else:
            dataset = torch.utils.data.TensorDataset(
                        torch.from_numpy(sinogram_array[:, None]),
                        torch.from_numpy(fbp_array[:, None]))

        return dataset
    else:
        return sinogram_array, fbp_array, ground_truth_array


def get_lotus_data(name, cfg):

    ray_trafos = get_ray_trafos(name, cfg,
                                return_torch_module=False)
    smooth_pinv_ray_trafo = ray_trafos['smooth_pinv_ray_trafo']

    sinogram = np.asarray(lotus.get_sinogram(
                    cfg.geometry_specs.ray_trafo_filename,
                    scale_to_fbp_max_1=cfg.test_data_scale_to_fbp_max_1))
    if 'angles_subsampling' in cfg.geometry_specs:
        sinogram = sinogram[cfg.geometry_specs.angles_subsampling.start:
                            cfg.geometry_specs.angles_subsampling.stop:
                            cfg.geometry_specs.angles_subsampling.step, :]

    fbp = np.asarray(smooth_pinv_ray_trafo(sinogram))

    ground_truth = None
    if cfg.ground_truth_filename is not None:
        ground_truth = lotus.get_ground_truth(cfg.ground_truth_filename)

    return sinogram, fbp, ground_truth
