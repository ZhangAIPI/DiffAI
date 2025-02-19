# load AlexNet model and train it on 2D data
import os
import sys
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))
import torch
import torch.nn as nn
import torch.optim as optim
import torchvision.models as models
from torchvision import transforms
import os
import time
import copy
import numpy as np
from dataloader_hkl_no import Dataset
from torch.utils.data import  DataLoader
import wandb
from tqdm import tqdm
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
# wandb.init(project="xrd_2d_alexnet")

def accuracy_topk(output, target, maxk):
    """Computes the precision@k for the specified values of k"""
    batch_size = target.size(0)
    # import pdb;pdb.set_trace()
    _, pred = output.topk(maxk, 1, True, True)
    pred = pred.t()
    # import pdb;pdb.set_trace()
    correct = pred.eq(target.cuda().view(1, -1).expand_as(pred))

    res = correct[:maxk].reshape(-1).float().sum(0)
    return res



class HKL_model(nn.Module):
    def __init__(self, model):
        super(HKL_model, self).__init__()
        self.model = model
        self.embedding_layer_h = nn.Embedding(5, 4096)
        self.embedding_layer_k = nn.Embedding(5, 4096)
        self.embedding_layer_l = nn.Embedding(5, 4096)
        self.proj_linear = nn.Sequential(
            nn.Linear(512 * 7 * 7, 4096),
            nn.ReLU(True),
            nn.Dropout(p=0.5),
            nn.Linear(4096, 4096),
            nn.ReLU(True),  nn.Dropout(p=0.5))
        self.cls = nn.Linear(4096, 230)
        self.cls7 = nn.Linear(4096, 7)
        self.h_predict = nn.Linear(4096, 5)
        self.k_predict = nn.Linear(4096, 5)
        self.l_predict = nn.Linear(4096, 5)

    def forward(self, x, h, k, l):
        x = self.model.features(x)
        x = self.model.avgpool(x)
        x = torch.flatten(x,1)
        h = self.embedding_layer_h(h)
        k = self.embedding_layer_k(k)
        l = self.embedding_layer_l(l)
        position_embedding = h + k + l
        position_featuer = nn.Sigmoid()(position_embedding)
        fx = self.proj_linear(x) * position_featuer
        x = self.cls(fx)
        ph = self.h_predict(fx)
        pk = self.k_predict(fx)
        pl = self.l_predict(fx)
        x7 = self.cls7(fx)
        return x, x7, ph, pk, pl

"""
Crystal system (7ways)	        space group (230ways)
Cubic	                               195 to 230
Hexagonal	                      168 to 194
Trigonal	                              143 to 167
Tetragonal	                     75 to 142
Orthorhombic	            16 to 74
Monoclinic	                    3 to 15
Triclinic	                            1 to 2 
"""
label_map = {
    0: list(range(194, 230)),
    1: list(range(167, 194)),
    2: list(range(142, 167)),
    3: list(range(74, 142)),
    4: list(range(15, 74)),
    5: list(range(2, 15)),
    6: list(range(0, 2)), 
}



def transform_from_230_to_7(label):
    for key in label_map:
        if label in label_map[key]:
            return key
    return None

# generate a map from 230 to 7
label_map_230_to_7 = {}
for key in label_map:
    for value in label_map[key]:
        label_map_230_to_7[value] = key

if __name__ == "__main__":
    
    # root_paths = ['/scratch/zzh136/xrd_2d/another_test/_011', '/scratch/zzh136/xrd_2d/another_test/_u1', '/scratch/zzh136/xrd_2d/another_test/_u2']
    # val_paths = ['/scratch/zzh136/xrd_2d/another_test/_011/test_files.xlsx', '/scratch/zzh136/xrd_2d/another_test/_u1/test_files.xlsx', '/scratch/zzh136/xrd_2d/another_test/_u2/test_files.xlsx']
    # appds = ['/meta']
    # root_path = "/scratch/zzh136/xrd_2d/redo/redo10"
    # train_path = "/scratch/zzh136/xrd_2d/redo/redo10/train_files.xlsx"
    # val_path = "/scratch/zzh136/xrd_2d/redo/redo10/test_files.xlsx"
    root_path  = '/scratch/zzh136/xrd_2d/defect/'
    model_paths = ["/scratch/zzh136/xrd_2d/axis20_data/ckpt/vanilla_vgg19.pth"]
    for model_path in model_paths:
        print('begin initialization')
        # print("root_path: ", root_paths[num])
        # print("model path: ", model_path)
        # root_path = root_paths[num]
        # train_path = train_paths[num]
        # val_path = val_paths[num]
        # print('begin initialization')
        # label_path = os.path.join(root_path, "label.xlsx")
        # train_dataset = Dataset(root_path = root_path, img_path = train_path, label_path = label_path)
        val_dataset = Dataset(root_path = root_path, img_path = None, fmt=True)
        # train_loader = DataLoader(train_dataset, batch_size=128, shuffle=True, num_workers=4)
        print('build val dataset ok')
        val_loader = DataLoader(val_dataset, batch_size=128, shuffle=True, num_workers=8)
        print('build val loader ok')
        model = models.vgg19(pretrained=False, num_classes=230)
        optimazier = optim.SGD(model.parameters(), lr=0.001, momentum=0.9)
        criterion = nn.CrossEntropyLoss()
        device =  torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        # model.load_state_dict(torch.load("/scratch/zzh136/xrd_2d/redo/redo4/ckpt/pretrained_alexnet_hkl.pth"))
        # 111: /scratch/zzh136/xrd_2d/output111/ckpt/vanilla_alexnet.pth on 001: 0.0533    on 111: 0.7838
        # 001: /scratch/zzh136/xrd_2d/output/ckpt/vanilla_alexnet.pth    on 001: 0.7496    on 111: 0.0493  on 100: 0.2681 on 010
        model=HKL_model(model)
        model.load_state_dict(torch.load("/scratch/zzh136/xrd_2d/axis20_data/ckpt/pretrained_vgg19_hkl_noflip_7.pth"))
        # 111: /scratch/zzh136/xrd_2d/output111/ckpt/vanilla_alexnet.pth on 001: 0.0533    on 111: 0.7838
        # 001: /scratch/zzh136/xrd_2d/output/ckpt/vanilla_alexnet.pth    on 001: 0.7496    on 111: 0.0493  on 100: 0.2681 on 010
        model = model.to(device)
        epochs = 100
        batch_size = 128
        # train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=4)
        val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=True, num_workers=4)
        # model_save_path = os.path.join(root_path, "ckpt", "vanilla_alexnet.pth")
        # if not os.path.exists(os.path.dirname(model_save_path)):
        #     os.makedirs(os.path.dirname(model_save_path))
        # statistic the accuracy for each class
        class_correct = list(0. for i in range(230))
        class_total = list(0. for i in range(230))
        class_correct = np.array(class_correct)
        class_total = np.array(class_total)
        class_correct = torch.tensor(class_correct)
        class_total = torch.tensor(class_total)
        class_correct = class_correct.to(device)
        class_total = class_total.to(device)
        class_entropy = list(0. for i in range(230))
        class_entropy = np.array(class_entropy)
        class_entropy = torch.tensor(class_entropy)
        model.eval()
        running_loss = 0.0
        running_correct = 0.0
        entropy_list_w_c = [[],[]]
        N = 0
        running_correct_5 = 0.0
        confusion_matrix = torch.zeros(230, 230)
        top5_preds_list = []
        all_file_paths = []
        preds7_list = []
        for i, data in tqdm(enumerate(val_loader, 0)):
            inputs, labels, h,k,l, paths = data
            inputs, labels = inputs.to(device), labels.to(device)
            h,k,l = h.to(device), k.to(device), l.to(device)
            N += inputs.size(0)
            outputs, outputs7,_,_,_ = model(inputs,h,k,l)
            # loss = criterion(outputs, labels)
            # running_loss += loss.item()
            _, preds = torch.max(outputs, 1)
            outputs = torch.nn.functional.softmax(outputs, dim=1)
            
            _,preds_7 = torch.max(outputs7, 1)
            
            labels = labels.cpu()
            preds = preds.cpu()
            preds7_list.extend(preds_7.cpu().numpy().tolist())
            # entropies = -torch.sum(outputs * torch.log(outputs), dim=1).detach().cpu().numpy()
            # import pdb;pdb.set_trace()
            # get the top 5 labels
            _, top5_preds = torch.topk(outputs, 5, 1)
            top5_preds = top5_preds + 1
            top5_preds = top5_preds.cpu().detach().numpy().tolist()
            top5_preds_list.extend(top5_preds)
            all_file_paths.extend(paths)
    # generate a datafram to store the top 5 predictions  the first column is the file name, the second to the sixth column is the top 5 predictions
    import pandas as pd
    top5_preds_df = pd.DataFrame(top5_preds_list)
    top5_preds_df.insert(0, 'file_name', all_file_paths)
    top5_preds_df.to_csv('defect_top5_preds.csv')
    print('top5_preds.csv saved')
    
    preds7_df = pd.DataFrame(preds7_list)
    preds7_df.insert(0, 'file_name', all_file_paths)
    preds7_df.to_csv('defect_preds7.csv')
    print('preds7.csv saved')
    
    # import pdb;pdb.set_trace()
    # for i in range(inputs.size(0)):
    #     label = labels[i]
    #     pred = preds[i]
    #     class_correct[label] += (label == pred)
    #     class_total[label
