from __future__ import print_function
import torch.nn as nn
# from util.torch.nn import set_determinsitic_run
import torch
import torch.nn.parallel
import torch.optim as optim
import torch.utils.data
from pytorch_lightning import seed_everything
from models.pointnet.pointnet.dataset import ShapeNetDataset, ModelNetDataset, FaustDataset
import models.pointnet.pointnet.model as mod
import torch.nn.functional as F
import numpy as np
from pytorch_lightning import loggers as pl_loggers

# import lightning.assets.plotter


# very buggy - Two instances of pytorch lightning working together
# set_determinsitic_run()     # Set a universal random seed

if __name__ == "__main__":
    import pytorch_lightning as pl

    class PointNetCls_light(pl.LightningModule):

        def __init__(self, hparams):
            super(PointNetCls_light, self).__init__()

            self.batchsize = hparams.get('batchsize', 32)
            self.num_points = hparams.get('num_points', 2500)
            self.workers = hparams.get('workers', 4)
            self.dataset_type = hparams.get('dataset_type', 'shapenet')
            self.feature_transform = hparams.get('feature_transform', False)
            self.classes = hparams['classes']
            self.dataset = hparams['dataset_loc']
<<<<<<< HEAD:temp_archive/models/pointnet/lightning_train.py

            # self.plotter_class = hparams.get('plotter', False)
            # self._init_training_assets()
=======
>>>>>>> de0a54e05ec35ba32af815b09617cbba8097b650:models/pointnet.pytorch-master/lightning_train.py

            self.feat = mod.PointNetfeat(global_feat=True, feature_transform=self.feature_transform)
            self.fc1 = nn.Linear(1024, 512)
            self.bn1 = nn.BatchNorm1d(512)
            self.relu = nn.ReLU()
            self.fc2 = nn.Linear(512, 256)
            self.dropout = nn.Dropout(p=0.3)
            self.bn2 = nn.BatchNorm1d(256)
            self.relu = nn.ReLU()
            self.fc3 = nn.Linear(256, self.classes)

        def forward(self, x):
            x, trans, trans_feat = self.feat(x)
            x = F.relu(self.bn1(self.fc1(x)))
            x = F.relu(self.bn2(self.dropout(self.fc2(x))))
            x = self.fc3(x)
            return F.log_softmax(x, dim=1), trans, trans_feat

        def prepare_data(self):
            self.outf = 'cls' # output folder - do we need this?

            funcdict = {
                'ShapeNetDataset': ShapeNetDataset,
                'FaustDataset': FaustDataset,
                'ModelNetDataset': ModelNetDataset,
            }
            if self.dataset_type == 'shapenet':
                dataset = 'ShapeNetDataset'
            elif self.dataset_type == 'faust':
                dataset = 'FaustDataset'
            else:
                dataset = 'ModelNetDataset'

            self.train_dataset = funcdict[dataset](
                root=self.dataset,
                classification=True,
                split='train',
                npoints=self.num_points)

            # self.val_dataset = funcdict[dataset](
            #     root=self.dataset,
            #     classification=True,
            #     split='val',
            #     npoints=self.num_points,
            #     data_augmentation=False)

            self.test_dataset = funcdict[dataset](
                root=self.dataset,
                classification=True,
                split='test',
                npoints=self.num_points,
                data_augmentation=False)

        def train_dataloader(self):
            return torch.utils.data.DataLoader(self.train_dataset,
                                               batch_size=self.batchsize,
                                               shuffle=True,
                                               num_workers=int(self.workers))

        # def val_dataloader(self): # debugging - dont forget to change to val_dataset
        #     return torch.utils.data.DataLoader(self.val_dataset,
        #                                        batch_size=self.batchsize,
        #                                        num_workers=int(self.workers))

        def test_dataloader(self):
            return  torch.utils.data.DataLoader(self.test_dataset,
                                                batch_size=self.batchsize,
                                                shuffle=False,
                                                num_workers=int(self.workers))


        def configure_optimizers(self):
            optimizer = optim.Adam(self.parameters(), lr=1e-3, betas=(0.9, 0.999))
            scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=20, gamma=0.5)
            return [optimizer], [scheduler]

        def cross_entropy_loss(self, pred, target):
            return F.nll_loss(pred, target)

        def training_step(self, batch, batch_idx):
            points, target = batch
            target = target[:, 0]
            points = points.transpose(2, 1)
            points = points.to(self.device)
            pred, trans, trans_feat = self.forward(points)

            loss = self.cross_entropy_loss(pred, target)
            if self.feature_transform:
                loss += mod.feature_transform_regularizer(trans_feat) * 0.001

            pred_choice = pred.data.max(1)[1]
            correct = pred_choice.eq(target.data).sum()
            acc = correct.item() / self.batchsize
            logs = {'train loss': loss, 'train_acc': acc}
            return {'loss': loss, 'log': logs, 'train_acc': acc}

        # def validation_step(self, batch, batch_idx):
        #     points, target = batch # data
        #     target = target[:, 0]
        #     points = points.transpose(2, 1)
        #     points = points.to(self.device)
        #     pred, _, _ = self.forward(points)
        #     loss = self.cross_entropy_loss(pred, target)
        #
        #     pred_choice = pred.data.max(1)[1]
        #     correct = pred_choice.eq(target.data).sum()
        #     acc = correct.item() / self.batchsize
        #     # print(" Validation step accuracy is ", acc)
        #     test_log = {'val_acc': acc, 'val_loss': loss}
        #     return {'val_loss': loss, 'val_acc': acc, 'log': test_log}

        # def validation_end(self, outputs):
        #     avg_loss = torch.stack([x['val_loss'] for x in outputs]).mean()
        #     val_acc = np.stack([x['val_acc'] for x in outputs]).mean()
        #     end_log = {'val_loss': avg_loss,'val_acc':val_acc}
        #     return {'val_loss': avg_loss, 'val_acc':val_acc, 'log': end_log }

        def test_step(self, batch, batch_idx):
            points, target = batch
            target = target[:, 0]
            points = points.transpose(2, 1)

            points = points.to(self.device)
            target = target.to(self.device)

            pred, _, _ = self.forward(points)
            loss = self.cross_entropy_loss(pred, target)

            pred_choice = pred.data.max(1)[1]
            correct = pred_choice.eq(target.data).sum()
            acc = correct.item() / self.batchsize
            test_log = {'test_acc': acc,'test_loss':loss}
            return {'test_loss': loss, 'test_acc': acc, 'log': test_log}

        def test_end(self, outputs):
            avg_loss = torch.stack([x['test_loss'] for x in outputs]).mean()
            test_acc = np.stack([x['test_acc'] for x in outputs]).mean()
            end_log = {'test_loss_mean': avg_loss, 'test_acc_mean': test_acc}
            print('\nAvg test loss: ',avg_loss,'\n','Avg test acc: ', test_acc)
            return {'test_loss_mean': avg_loss, 'test_acc_mean': test_acc, 'log': end_log}

        def finalize(self):
            pass
            # Called after all epochs, for cleanup
            # If needed, send the final report via email:
            # if self.emailer is not None:  # Long enough train, or test only
            #     if self.nn.current_epoch >= self.hp.MIN_EPOCHS_TO_SEND_EMAIL_RECORD or self.testing_only:
            #         log.info("Sending zip with experiment specs to configured inbox")
            #         self.emailer.send_report(self.trainer.final_result_str)
            #     else:
            #         log.info("Model has not been trained for enough epochs - skipping attachment send")

            # if self.plt is not None and self.plt.is_alive():
            #     self.plt.finalize()
            # if self.tb_sup is not None:
            #     self.tb_sup.finalize()

            # log.info("Cleaning up GPU memory")
            # torch.cuda.empty_cache()

    # train
    # to open tensorboard, run this command in terminal and open the browser:
    # tensorboard --logdir ./logs/
    ## Define train parameters:
    # full path
    dataset_loc = r'/home/jack/OneDrive/Studies/Undergrad_Project/data/MPI-FAUST/training/registrations'
    dataset_loc = r'C:\Users\RoeePC\Desktop\proj\DeepAdv3D\data\MPI-FAUST\training\registrations'  # FAUST roee's PC
    # dataset_loc = r'D:\Roee_Yevgeni\pointnet.pytorch\shapenetcore_partanno_segmentation_benchmark_v0\shapenetcore_partanno_segmentation_benchmark_v0'
    # dataset_loc = r'/home/jack/OneDrive/Studies/Undergrad_Project/data/shapenetcore_partanno_segmentation_benchmark_v0'

    hp = {
        "dataset_loc": dataset_loc,
        "classes": 10,
        "feature_transform": False,
<<<<<<< HEAD:temp_archive/models/pointnet/lightning_train.py
        "batchsize": 8,                # for shapenet 32
=======
        "batchsize": 4,
>>>>>>> de0a54e05ec35ba32af815b09617cbba8097b650:models/pointnet.pytorch-master/lightning_train.py
        "num_points": 2500,
        "workers": 4,
        "dataset_type": 'faust'
    }
<<<<<<< HEAD:temp_archive/models/pointnet/lightning_train.py
    seed_everything(42)

    logging_loc = r'/home/jack/OneDrive/Studies/Undergrad_Project/data/logs/'
    tb_logger = pl_loggers.TensorBoardLogger(logging_loc, name='pointnet classifier')

    model = PointNetCls_light(hp)
    trainer = pl.Trainer(logger=tb_logger, max_epochs=5, deterministic=True, log_save_interval=10, row_log_interval=10, fast_dev_run=False,)# gpus=-1)
    trainer.fit(model) # train
    trainer.test(model)

    #test
    # checkpoint_loc = r'/home/jack/OneDrive/Studies/Undergrad_Project/data/logs/default/version_13/checkpoints/epoch=9.ckpt'
    # hp['batchsize'] = 1 # for testing
    # model = PointNetCls_light.load_from_checkpoint(checkpoint_loc, **hp)
    # trainer.test(model)
=======

    # logging_loc = r'/home/jack/OneDrive/Studies/Undergrad_Project/data/logs/'
    logging_loc = r'C:\Users\RoeePC\Desktop\proj\DeepAdv3D\data\logs'
    tb_logger = pl_loggers.TensorBoardLogger(logging_loc)

    # model = PointNetCls_light(hp)
    trainer = pl.Trainer(logger=tb_logger, max_epochs=10, log_save_interval=20, fast_dev_run=False, gpus=-1)
    # trainer.fit(model) # train

    #test
    # checkpoint_loc = r'/home/jack/OneDrive/Studies/Undergrad_Project/data/logs/default/version_13/checkpoints/epoch=9.ckpt'
    checkpoint_loc = r'C:\Users\RoeePC\Desktop\proj\DeepAdv3D\data\logs\default\version_0\checkpoints\epoch=89.ckpt'
    hp['batchsize'] = 1  # for testing
    model = PointNetCls_light.load_from_checkpoint(checkpoint_loc, **hp)
    trainer.test(model)
>>>>>>> de0a54e05ec35ba32af815b09617cbba8097b650:models/pointnet.pytorch-master/lightning_train.py

    # %load_ext tensorboard
    # %tensorboard --logdir lightning_logs/