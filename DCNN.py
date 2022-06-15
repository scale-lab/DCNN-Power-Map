# -*- coding: utf-8 -*-
"""
DCNN power map estimation with an output resolution of 14x12.
"""

#importing the libraries

import torch
from torch import nn
from tqdm.auto import tqdm
from torchvision import transforms
from torchvision.datasets import MNIST
from torchvision.utils import make_grid
from torch.utils.data import DataLoader
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn import preprocessing
import math as m
from statistics import mean
import random
import seaborn as sns; sns.set_theme()
torch.manual_seed(0) # Set for our testing purposes, please do not change!

#function that retrieves the next batch
def next_batch(images,sensors,batchnum):
  x= images[batchnum*batch_size:batch_size*(batchnum+1)]
  y= sensors[batchnum*batch_size:batch_size*(batchnum+1)]
  x=x.astype(np.float32)
  y=y.astype(np.float32)
  return torch.tensor(x.values),torch.tensor(y.values)

#The DCNN network -> it generates/estimates the power maps.
class Generator(nn.Module):
    def __init__(self, input_dim=10, im_chan=1, hidden_dim=32):
        super(Generator, self).__init__()
        self.input_dim = input_dim
        # Build the neural network
        self.gen = nn.Sequential(
            self.make_gen_block(input_dim, hidden_dim * 4, kernel_size=(2,3) ),
            self.make_gen_block(hidden_dim * 4, hidden_dim * 4, kernel_size=(3,3)),
            self.make_gen_block(hidden_dim * 4, hidden_dim * 2, kernel_size=(4,5), stride=2, padding=(1,2)),
            self.make_gen_block(hidden_dim * 2, im_chan,kernel_size=(5,6), final_layer=True),
        )
        self.fc1= nn.Linear(168,336,bias=True)
        self.final_relu=nn.ReLU()
        self.fc2= nn.Linear(336,168,bias=True)

    def make_gen_block(self, input_channels, output_channels, kernel_size, stride=1, padding=(0,0),final_layer=False):
        if not final_layer:
            return nn.Sequential(
                nn.ConvTranspose2d(input_channels, output_channels, kernel_size, stride,padding),
                #nn.BatchNorm2d(output_channels),
                #[batch_size, 1, 12, 12] -> [batch_size]
                nn.ReLU(inplace=True),


            )
        else:
            return nn.Sequential(
                nn.ConvTranspose2d(input_channels, output_channels, kernel_size, stride,padding),
                nn.ReLU(),
            )

    def forward(self, noise):
        x = noise.view(len(noise), self.input_dim, 1, 1)
        output = self.gen(x)
        output = output.reshape(output.shape[0],-1)
        output= self.fc1(output)
        output= self.final_relu(output)
        return self.fc2(output)

# defining the loss and the different hyper-parameters
criterion = nn.MSELoss()
n_epochs = 1000
batch_size = 32
lr = 0.0002
#lr = 0.00005
generator_input_dim=28
train_data_ratio=0.8
shuffle_seed=4

# Initializing the DCNN
gen = Generator(input_dim=generator_input_dim)
gen_opt = torch.optim.Adam(gen.parameters(), lr=lr)
#gen_opt = torch.optim.SGD(gen.parameters(), lr=lr)
def weights_init(m):
    if isinstance(m, nn.Conv2d) or isinstance(m, nn.ConvTranspose2d):
        torch.nn.init.normal_(m.weight, 0.0, 0.02)
    if isinstance(m, nn.BatchNorm2d):
        torch.nn.init.normal_(m.weight, 0.0, 0.02)
        torch.nn.init.constant_(m.bias, 0)

gen = gen.apply(weights_init)

# function to adjust the learning rate (not used)
def adjust_learning_rate(optimizer, epoch,lr):
    """Sets the learning rate to the initial LR decayed by 10 every 30 epochs"""
    lr_ad = lr * (0.5 ** (epoch // 200))
    for param_group in optimizer.param_groups:
      if param_group['lr']!=lr_ad:
        print('learning rate adjusted to:',lr_ad)
      param_group['lr'] = lr_ad

# loading, processing and normalizing the data
images=pd.read_csv("p_images.csv")
sensors=pd.read_csv("p_sensors2.csv")
sensors2=preprocessing.normalize(sensors, axis=0)
#sensors2.iloc[:,0]=sensors.iloc[:,0]
sensors2=pd.DataFrame(sensors2)
sensors2.iloc[:,0]=sensors.iloc[:,0]
sensors=sensors2

num_samples=sensors.shape
ind_list = [i for i in range(num_samples[0])]
random.Random(shuffle_seed).shuffle(ind_list)

train_indices=ind_list[0:m.floor(num_samples[0]*train_data_ratio)]
test_indices=ind_list[m.floor(num_samples[0]*train_data_ratio):]

images_train=images.iloc[train_indices]
sensors_train=sensors.iloc[train_indices]

images_test=images.iloc[test_indices]
sensors_test=sensors.iloc[test_indices]


# training the DCNN
cur_step = 0
generator_losses = []
num_batches=m.floor(num_samples[0]*train_data_ratio/batch_size)

sensors.shape

for epoch in range(n_epochs):
   for i in range(num_batches):
        x,y=next_batch(images_train,sensors_train,i)
        #x=torch.reshape(x, (batch_size, 1,12,14))
        x=np.reshape(x,(batch_size,-1),order='A')
        #x=x.reshape(batch_size,-1)
        fake = gen(y)
        gen_opt.zero_grad()

        gen_loss = criterion(x,fake)
        gen_loss.backward()
        gen_opt.step()
        adjust_learning_rate(gen_opt, epoch,lr)
        # Keep track of the generator losses
        generator_losses += [gen_loss.item()]
   print("Epoch:",epoch)
   print(mean(generator_losses))
   generator_losses = []

# Saving the model
print("Model's state_dict:")
for param_tensor in gen.state_dict():
    print(param_tensor, "\t", gen.state_dict()[param_tensor].size())

torch.save(gen.state_dict(), './model')

# Testing the model
num_batches=m.floor(num_samples[0]*(1-train_data_ratio)/batch_size)
criterion = nn.L1Loss()
generator_losses = []
avg_power=[]

for i in range(num_batches):
  x,y=next_batch(images_test,sensors_test,i)
  x=np.reshape(x,(batch_size,-1),order='A')
  fake = gen(y)
  fake[fake<0] = 0
  gen_loss = criterion(x,fake)

  # Keep track of the generator losses
  generator_losses += [gen_loss.item()]
  avg_power += [1000*np.mean(x.detach().numpy())]

# computing the average error
1000*np.mean(generator_losses)

# Optional part
# Generates and saves the power map estimation and true values to csv files.

images=pd.read_csv("p_images.csv")
sensors=pd.read_csv("p_sensors2.csv")
sensors2=preprocessing.normalize(sensors, axis=0)
sensors2=pd.DataFrame(sensors2)
sensors2.iloc[:,0]=sensors.iloc[:,0]
sensors=sensors2


images_bench=images_train
sensors_bench=sensors_train
num_samples=sensors_bench.shape

num_batches=m.floor(num_samples[0]/batch_size)
criterion = nn.L1Loss()
generator_losses = []
avg_power=[]

for i in range(num_batches):
  if i==0:
    x,y=next_batch(images_bench,sensors_bench,i)
    x=np.reshape(x,(batch_size,-1),order='A')
    fake = gen(y)
    fake[fake<0] = 0
    fake_all=fake
    x_all=x
  else:
    x,y=next_batch(images_bench,sensors_bench,i)
    x=np.reshape(x,(batch_size,-1),order='A')
    fake = gen(y)
    fake[fake<0] = 0
    fake_all=torch.cat((fake_all, fake), 0)
    x_all=torch.cat((x_all, x), 0)

  gen_loss = criterion(x,fake)

  # Keep track of the generator losses
  generator_losses += [gen_loss.item()]
  avg_power += [1000*np.mean(x.detach().numpy())]

1000*np.mean(generator_losses)

np.mean(avg_power)

np.savetxt('R_train.csv', x_all.detach().numpy(), delimiter=',')
np.savetxt('F_train.csv', fake_all.detach().numpy(), delimiter=',')
