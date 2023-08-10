import sys
import typing as T
from os.path import splitext
from pathlib import Path

from .utils.log import logger


class UFishCLI():
    def __init__(
            self,
            cuda: bool = True,
            local_store_path: str = '~/.ufish/',
            weights_file_name: str = 'v1.1-gaussian_target.pth',
            ):
        from .api import UFish
        self._ufish = UFish(
            cuda=cuda,
            default_weights_file=weights_file_name,
            local_store_path=local_store_path,
        )
        self._weights_loaded = False

    def set_log_level(
            self,
            level: str = 'INFO'):
        """Set the log level."""
        logger.remove()
        logger.add(
            sys.stderr, level=level,
        )
        return self

    def load_weights(
            self,
            weights_path: T.Optional[str] = None,
            weights_file: T.Optional[str] = None,
            max_retry: int = 8,
            force_download: bool = False,
            ):
        """Load weights from a local file or the internet.

        Args:
            weights_path: The path to the weights file.
            weights_file: The name of the weights file on the internet.
                See https://huggingface.co/GangCaoLab/U-FISH/tree/main
                for available weights files.
            max_retry: The maximum number of retries to download the weights.
            force_download: Whether to force download the weights.
        """
        if weights_path is not None:
            self._ufish.load_weights(weights_path)
        else:
            self._ufish.load_weights_from_internet(
                weights_file=weights_file,
                max_retry=max_retry,
                force_download=force_download,
            )
        self._weights_loaded = True
        return self

    def enhance_img(
            self,
            input_img_path: str,
            output_img_path: str,
            ):
        """Enhance an image."""
        from skimage.io import imread, imsave
        if not self._weights_loaded:
            self.load_weights()
        logger.info(f'Enhancing {input_img_path}')
        img = imread(input_img_path)
        enhanced = self._ufish.enhance_img(img)
        imsave(output_img_path, enhanced)
        logger.info(f'Saved enhanced image to {output_img_path}')

    def call_spots_cc_center(
            self,
            enhanced_img_path: str,
            output_csv_path: str,
            binary_threshold: T.Union[str, float] = 'otsu',
            cc_size_thresh: int = 20
            ):
        """Call spots by finding connected components
        and taking the centroids.

        Args:
            enhanced_img_path: Path to the enhanced image.
            output_csv_path: Path to the output csv file.
            binary_threshold: The threshold for binarizing the image.
            cc_size_thresh: Connected component size threshold.
        """
        from skimage.io import imread
        img = imread(enhanced_img_path)
        logger.info(f'Calling spots in {enhanced_img_path}')
        logger.info(
            f'Parameters: binary_threshold={binary_threshold}, ',
            f'cc_size_thresh={cc_size_thresh}')
        pred_df = self._ufish.call_spots_cc_center(
            img,
            binary_threshold=binary_threshold,
            cc_size_thresh=cc_size_thresh)
        pred_df.to_csv(output_csv_path, index=False)
        logger.info(f'Saved predicted spots to {output_csv_path}')

    def call_spots_local_maxima(
            self,
            enhanced_img_path: str,
            output_csv_path: str,
            connectivity: int = 2,
            intensity_threshold: float = 0.1,
            ):
        """Call spots by finding local maxima.

        Args:
            enhanced_img_path: Path to the enhanced image.
            output_csv_path: Path to the output csv file.
            connectivity: The connectivity for finding local maxima.
            intensity_threshold: The threshold for the intensity.
        """
        from skimage.io import imread
        img = imread(enhanced_img_path)
        logger.info(f'Calling spots in {enhanced_img_path}')
        logger.info(
            f'Parameters: connectivity={connectivity}, ',
            f'intensity_threshold={intensity_threshold}')
        pred_df = self._ufish.call_spots_local_maxima(
            img,
            connectivity=connectivity,
            intensity_threshold=intensity_threshold)
        pred_df.to_csv(output_csv_path, index=False)
        logger.info(f'Saved predicted spots to {output_csv_path}')

    def pred_2d_img(
            self,
            input_img_path: str,
            output_csv_path: str,
            enhanced_output_path: T.Optional[str] = None,
            connectivity: int = 2,
            intensity_threshold: float = 0.1,
            ):
        """Predict spots in a 2d image.

        Args:
            input_img_path: Path to the input image.
            output_csv_path: Path to the output csv file.
            enhanced_output_path: Path to the enhanced image.
            connectivity: The connectivity for finding local maxima.
            intensity_threshold: The threshold for the intensity.
        """
        from skimage.io import imread, imsave
        if not self._weights_loaded:
            self.load_weights()
        logger.info(f'Predicting {input_img_path}.')
        img = imread(input_img_path)
        pred_df, enhanced = self._ufish.pred_2d(
            img,
            connectivity=connectivity,
            intensity_threshold=intensity_threshold,
            return_enhanced_img=True)
        pred_df.to_csv(output_csv_path, index=False)
        logger.info(f'Saved predicted spots to {output_csv_path}')
        if enhanced_output_path is not None:
            imsave(enhanced_output_path, enhanced)
            logger.info(f'Saved enhanced image to {enhanced_output_path}')

    def pred_2d_imgs(
            self,
            input_dir: str,
            output_dir: str,
            save_enhanced_img: bool = True,
            connectivity: int = 2,
            intensity_threshold: float = 0.1,
            ):
        """Predict spots in a directory of 2d images.

        Args:
            input_dir: Path to the input directory.
            output_dir: Path to the output directory.
            save_enhanced_img: Whether to save the enhanced image.
            connectivity: The connectivity for finding local maxima.
            intensity_threshold: The threshold for the intensity.
        """
        if not self._weights_loaded:
            self.load_weights()
        in_dir_path = Path(input_dir)
        out_dir_path = Path(output_dir)
        out_dir_path.mkdir(parents=True, exist_ok=True)
        logger.info(f'Predicting images in {in_dir_path}')
        logger.info(f'Saving results to {out_dir_path}')
        for input_path in in_dir_path.iterdir():
            input_prefix = splitext(input_path.name)[0]
            output_path = out_dir_path / (input_prefix + '.pred.csv')
            enhanced_img_path = out_dir_path / (input_prefix + '.enhanced.tif')
            self.pred_2d_img(
                str(input_path),
                str(output_path),
                str(enhanced_img_path) if save_enhanced_img else None,
                connectivity=connectivity,
                intensity_threshold=intensity_threshold,
            )

    def plot_2d_pred(
            self,
            image_path: str,
            pred_csv_path: str,
            fig_save_path: T.Optional[str] = None,
            **kwargs
            ):
        """Plot the predicted spots on the image."""
        import pandas as pd
        from skimage.io import imread
        import matplotlib.pyplot as plt
        img = imread(image_path)
        pred_df = pd.read_csv(pred_csv_path)
        fig = self._ufish.plot_result(
            img, pred_df, **kwargs
        )
        if fig_save_path is not None:
            fig.savefig(fig_save_path)
            logger.info(f'Saved figure to {fig_save_path}.')
        else:
            plt.show()

    def plot_2d_eval(
            self,
            image_path: str,
            pred_csv_path: str,
            true_csv_path: str,
            cutoff: float = 3.0,
            fig_save_path: T.Optional[str] = None,
            **kwargs
            ):
        """Plot the evaluation result."""
        import pandas as pd
        from skimage.io import imread
        import matplotlib.pyplot as plt
        img = imread(image_path)
        pred_df = pd.read_csv(pred_csv_path)
        gt_df = pd.read_csv(true_csv_path)
        fig = self._ufish.plot_evaluate(
            img, pred_df, gt_df, cutoff=cutoff, **kwargs)
        if fig_save_path is not None:
            fig.savefig(fig_save_path)
            logger.info(f'Saved figure to {fig_save_path}.')
        else:
            plt.show()

    def train(
            self,
            train_dir: str,
            valid_dir: str,
            img_glob: str = '*.tif',
            coord_glob: str = '*.csv',
            target_process: str = 'gaussian',
            data_argu: bool = False,
            num_epochs: int = 50,
            batch_size: int = 8,
            lr: float = 1e-4,
            summary_dir: str = "runs/unet",
            model_save_path: str = "best_unet_model.pth",
            only_save_best: bool = True,
            ):
        """Train the U-Net model.

        Args:
            train_dir: The directory containing the training images
                and coordinates.
            valid_dir: The directory containing the validation images
                and coordinates.
            img_glob: The glob pattern for the image files.
            coord_glob: The glob pattern for the coordinate files.
            target_process: The target image processing method.
                'gaussian' or 'dialation'. default 'gaussian'.
            data_argu: Whether to use data augmentation.
            num_epochs: The number of epochs to train.
            batch_size: The batch size.
            lr: The learning rate.
            summary_dir: The directory to save the TensorBoard summary to.
            model_save_path: The path to save the best model to.
        """
        self._ufish.train(
            train_dir=train_dir,
            valid_dir=valid_dir,
            img_glob=img_glob,
            coord_glob=coord_glob,
            target_process=target_process,
            data_argu=data_argu,
            num_epochs=num_epochs,
            batch_size=batch_size,
            lr=lr,
            summary_dir=summary_dir,
            model_save_path=model_save_path,
            only_save_best=only_save_best,
        )
