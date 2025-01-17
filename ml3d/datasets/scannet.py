import open3d as o3d
import numpy as np
import os, argparse, pickle, sys
from os.path import exists, join, isfile, dirname, abspath, split
from pathlib import Path
from glob import glob
import logging
import yaml

from .base_dataset import BaseDataset
from ..utils import Config, make_dir, DATASET
from .utils import BEVBox3D

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(asctime)s - %(module)s - %(message)s',
)
log = logging.getLogger(__name__)


class Scannet(BaseDataset):
    """
    Scannet 3D dataset for Object Detection, used in visualizer, training, or test
    """

    def __init__(self,
                 dataset_path,
                 name='Scannet',
                 cache_dir='./logs/cache',
                 use_cache=False,
                 **kwargs):
        """
        Initialize
        Args:
            dataset_path (str): path to the dataset
            kwargs:
        """
        super().__init__(dataset_path=dataset_path,
                         name=name,
                         cache_dir=cache_dir,
                         use_cache=use_cache,
                         **kwargs)

        cfg = self.cfg

        self.name = cfg.name
        self.dataset_path = cfg.dataset_path
        self.num_classes = 18

        self.classes = [
            'cabinet', 'bed', 'chair', 'sofa', 'table', 'door', 'window',
            'bookshelf', 'picture', 'counter', 'desk', 'curtain',
            'refrigerator', 'showercurtrain', 'toilet', 'sink', 'bathtub',
            'garbagebin'
        ]
        self.cat2label = {cat: self.classes.index(cat) for cat in self.classes}
        self.label2cat = {self.cat2label[t]: t for t in self.cat2label}
        self.cat_ids = np.array(
            [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 16, 24, 28, 33, 34, 36, 39])
        self.cat_ids2class = {
            nyu40id: i for i, nyu40id in enumerate(list(self.cat_ids))
        }

        self.label_to_names = self.get_label_to_names()

        available_scenes = []
        files = os.listdir(dataset_path)
        for f in files:
            if 'scene' in f and f.endswith('.npy'):
                available_scenes.append(f[:12])

        available_scenes = list(set(available_scenes))

        resource_path = Path(__file__).parent / '_resources' / 'scannet'
        train_files = open(resource_path /
                           'scannetv2_train.txt').read().split('\n')[:-1]
        val_files = open(resource_path /
                         'scannetv2_val.txt').read().split('\n')[:-1]
        test_files = open(resource_path /
                          'scannetv2_test.txt').read().split('\n')[:-1]

        self.train_scenes = []
        self.val_scenes = []
        self.test_scenes = []

        for scene in available_scenes:
            if scene in train_files:
                self.train_scenes.append(join(self.dataset_path, scene))
            elif scene in val_files:
                self.val_scenes.append(join(self.dataset_path, scene))
            elif scene in test_files:
                self.test_scenes.append(join(self.dataset_path, scene))

        self.semantic_ids = [
            1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 16, 24, 28, 33, 34, 36,
            39
        ]

    def get_label_to_names(self):
        return self.label2cat

    @staticmethod
    def read_lidar(path):
        assert Path(path).exists()
        data = np.load(path)

        return data

    def read_label(self, scene):
        instance_mask = np.load(scene + '_ins_label.npy')
        semantic_mask = np.load(scene + '_sem_label.npy')
        bboxes = np.load(scene + '_bbox.npy')

        ## For filtering semantic labels to have same classes as object detection.
        # for i in range(semantic_mask.shape[0]):
        #     semantic_mask[i] = self.cat_ids2class.get(semantic_mask[i], 0)

        remapper = np.ones(150) * (-100)
        for i, x in enumerate(self.semantic_ids):
            remapper[x] = i

        semantic_mask = remapper[semantic_mask]

        objects = []
        for box in bboxes:
            name = self.label2cat[self.cat_ids2class[int(box[-1])]]
            center = box[:3]
            size = [box[3], box[5], box[4]]  # w, h, l

            yaw = 0.0
            objects.append(Object3d(name, center, size, yaw))

        return objects, semantic_mask, instance_mask

    def get_split(self, split):
        return ScannetSplit(self, split=split)

    def get_split_list(self, split):
        if split in ['train', 'training']:
            return self.train_scenes
        elif split in ['test', 'testing']:
            return self.test_scenes
        elif split in ['val', 'validation']:
            return self.val_scenes

        raise ValueError("Invalid split {}".format(split))

    def is_tested(self):
        pass

    def save_test_result(self):
        pass


class ScannetSplit():

    def __init__(self, dataset, split='train'):
        self.cfg = dataset.cfg

        self.path_list = dataset.get_split_list(split)

        log.info("Found {} pointclouds for {}".format(len(self.path_list),
                                                      split))

        self.split = split
        self.dataset = dataset

    def __len__(self):
        return len(self.path_list)

    def get_data(self, idx):
        scene = self.path_list[idx]

        pc = self.dataset.read_lidar(scene + '_vert.npy')
        feat = pc[:, 3:]
        pc = pc[:, :3]

        bboxes, semantic_mask, instance_mask = self.dataset.read_label(scene)

        data = {
            'point': pc,
            'feat': feat,
            'calib': None,
            'bounding_boxes': bboxes,
            'label': semantic_mask.astype(np.int32),
            'instance': instance_mask.astype(np.int32)
        }

        return data

    def get_attr(self, idx):
        pc_path = self.path_list[idx]
        name = Path(pc_path).name.split('.')[0]

        attr = {'name': name, 'path': str(pc_path), 'split': self.split}
        return attr


class Object3d(BEVBox3D):
    """
    Stores object specific details like bbox coordinates.
    """

    def __init__(self, name, center, size, yaw):
        super().__init__(center, size, yaw, name, -1.0)

        self.occlusion = 0.0


DATASET._register_module(Scannet)
